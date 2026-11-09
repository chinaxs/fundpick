"""会员排查（只读）。

客服处理问题时需要看到"这个人关注了什么、有没有交易、最近有没有反馈"，
但**不提供任何修改入口**：金额与份额只能由会员本人重新确认或作废后重录，
否则记账依据就断了。查看交易明细会写一条审计记录，回答"谁看过"。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.fund import Fund
from app.models.fund_favorite import FundFavorite
from app.models.fund_position import FundPosition
from app.models.fund_transaction import FundTransaction
from app.models.support import PasswordResetRequest
from app.repositories.audit_log import AuditLogRepository
from app.repositories.user import UserRepository
from app.schemas.support import (
    MemberPortfolioItem,
    MemberPortfolioRead,
    MemberPositionItem,
    MemberSupportRead,
)
from app.services.feedback import FeedbackService

DEFAULT_PORTFOLIO_LIMIT = 200


def _money(value: Decimal | float | None) -> float:
    return float(value or 0)


class MemberSupportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def overview(self, user_id: int) -> MemberSupportRead:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("会员不存在")

        favorites = await self._count(FundFavorite, user_id)
        transactions = await self._count(FundTransaction, user_id)
        positions = await self._count(FundPosition, user_id)
        pending_reset = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(PasswordResetRequest)
                    .where(
                        PasswordResetRequest.user_id == user_id,
                        PasswordResetRequest.token_hash.is_(None),
                        PasswordResetRequest.used_at.is_(None),
                    )
                )
            ).scalar_one()
            or 0
        )
        return MemberSupportRead(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            favorite_count=favorites,
            transaction_count=transactions,
            position_count=positions,
            open_feedback=await FeedbackService(self.session).open_count(user_id),
            pending_reset=pending_reset,
        )

    async def _count(self, model, user_id: int) -> int:
        stmt = select(func.count()).select_from(model).where(model.user_id == user_id)
        if hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def portfolio(
        self, user_id: int, limit: int = DEFAULT_PORTFOLIO_LIMIT
    ) -> MemberPortfolioRead:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("会员不存在")

        total = await self._count(FundTransaction, user_id)
        tx_rows = (
            await self.session.execute(
                select(FundTransaction, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundTransaction.fund_id)
                .where(
                    FundTransaction.user_id == user_id,
                    FundTransaction.deleted_at.is_(None),
                )
                .order_by(FundTransaction.confirmed_on.desc(), FundTransaction.id.desc())
                .limit(limit)
            )
        ).all()
        items = [
            MemberPortfolioItem(
                id=tx.id,
                fund_code=code,
                fund_name=name,
                kind=tx.kind,
                status=tx.status,
                confirmed_on=tx.confirmed_on,
                submitted_at=tx.submitted_at,
                shares=_money(tx.shares),
                amount=_money(tx.amount),
                fee=_money(tx.fee),
                nav=_money(tx.nav),
                record_source=tx.record_source,
                platform=tx.platform,
                voided_at=tx.voided_at,
            )
            for tx, code, name in tx_rows
        ]

        position_rows = (
            await self.session.execute(
                select(FundPosition, Fund.code, Fund.name, Fund.latest_nav)
                .join(Fund, Fund.id == FundPosition.fund_id)
                .where(
                    FundPosition.user_id == user_id,
                    FundPosition.deleted_at.is_(None),
                )
                .order_by(FundPosition.id.desc())
            )
        ).all()
        positions = []
        for position, code, name, latest_nav in position_rows:
            cost_nav = position.cost_nav or Decimal(0)
            shares = (position.amount / cost_nav) if cost_nav else Decimal(0)
            market_value = shares * latest_nav if latest_nav else None
            positions.append(
                MemberPositionItem(
                    fund_code=code,
                    fund_name=name,
                    shares=float(shares),
                    cost=_money(position.amount),
                    market_value=_money(market_value) if market_value is not None else None,
                    updated_at=position.updated_at,
                )
            )

        return MemberPortfolioRead(
            user_id=user_id,
            items=items,
            positions=positions,
            total=total,
            truncated=total > len(items),
        )

    async def record_view(
        self,
        *,
        staff_id: int,
        staff_username: str,
        user_id: int,
        path: str,
        ip: str | None = None,
    ) -> None:
        """记一条"查看会员交易"的审计，只记录事实，不写明细内容。"""
        await AuditLogRepository(self.session).record(
            user_id=staff_id,
            username=staff_username,
            action="read",
            resource="member_portfolio",
            resource_id=str(user_id),
            method="GET",
            path=path,
            ip=ip,
            detail="经授权的只读排查",
        )
        await self.session.commit()
