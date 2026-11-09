"""交易流水查询与写入；事务提交由业务服务持有。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.models.fund_nav import FundNav
from app.models.fund_position import FundPosition
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.trade_application import TradeApplication
from app.models.user import User


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.locked = False

    async def lock_member(self, user_id: int) -> None:
        """同一会员的成交与作废串行执行，包括尚无任何交易的首次买入。"""
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())
        self.locked = True

    def current(self, statement):
        """写入时用当前读，避免 MySQL 可重复读仍读到等待锁之前的快照。"""
        return statement.with_for_update() if self.locked else statement

    async def rows(self, user_id: int) -> list[tuple[FundTransaction, Fund]]:
        result = await self.session.execute(
            self.current(
                select(FundTransaction, Fund)
                .join(Fund, Fund.id == FundTransaction.fund_id)
                .where(FundTransaction.user_id == user_id, FundTransaction.deleted_at.is_(None))
                .order_by(FundTransaction.confirmed_on, FundTransaction.id)
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def flows(self, user_id: int) -> list[FundPortfolioFlow]:
        """本人全部公司行为，按生效日升序（重放用）。"""
        result = await self.session.execute(
            self.current(
                select(FundPortfolioFlow)
                .where(
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.deleted_at.is_(None),
                )
                .order_by(FundPortfolioFlow.effective_on, FundPortfolioFlow.id)
            )
        )
        return list(result.scalars().all())

    async def funds_by_ids(self, ids: list[int]) -> list[Fund]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Fund).where(Fund.id.in_(ids), Fund.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def find_fund(self, code: str) -> Fund | None:
        return (
            await self.session.execute(
                select(Fund).where(Fund.code == code, Fund.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

    async def held_codes(self, user_id: int) -> list[str]:
        """跨平台汇总有效份额；不能以最后一个平台的清仓快照代表整只基金。"""
        shares = func.sum(
            case(
                (FundTransaction.kind == "buy", FundTransaction.shares),
                else_=-FundTransaction.shares,
            )
        )
        result = await self.session.execute(
            select(Fund.code)
            .join(FundTransaction, FundTransaction.fund_id == Fund.id)
            .where(
                FundTransaction.user_id == user_id,
                FundTransaction.status == "confirmed",
                FundTransaction.deleted_at.is_(None),
            )
            .group_by(Fund.code)
            .having(shares > 0)
            .order_by(Fund.code)
        )
        return list(result.scalars())

    async def exact_nav(self, fund: Fund, day: date) -> Decimal | None:
        """仅返回指定确认日的净值，绝不以其他日期替代。"""
        value = (
            await self.session.execute(
                select(FundNav.unit_nav).where(FundNav.fund_id == fund.id, FundNav.nav_date == day)
            )
        ).scalar_one_or_none()
        if value is None and fund.latest_nav_date == day:
            value = fund.latest_nav
        return value

    async def by_request(self, user_id: int, key: str) -> FundTransaction | None:
        return (
            await self.session.execute(
                self.current(
                    select(FundTransaction).where(
                        FundTransaction.user_id == user_id, FundTransaction.request_key == key
                    )
                )
            )
        ).scalar_one_or_none()

    async def owned(self, user_id: int, transaction_id: int) -> FundTransaction | None:
        return (
            await self.session.execute(
                self.current(
                    select(FundTransaction).where(
                        FundTransaction.user_id == user_id, FundTransaction.id == transaction_id
                    )
                )
            )
        ).scalar_one_or_none()

    async def legacy(self, user_id: int, position_id: int) -> FundPosition | None:
        return (
            await self.session.execute(
                self.current(
                    select(FundPosition).where(
                        FundPosition.id == position_id,
                        FundPosition.user_id == user_id,
                        FundPosition.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()

    async def original_legacy(self, position_id: int) -> FundPosition | None:
        return await self.session.get(FundPosition, position_id)

    def add(self, trade: FundTransaction) -> None:
        self.session.add(trade)

    async def remove_for_user(self, user_id: int) -> None:
        """注销账号时清除个人模拟交易明细，调用方统一提交。"""
        await self.session.execute(
            delete(FundTransaction).where(FundTransaction.user_id == user_id)
        )
        await self.session.execute(
            delete(TradeApplication).where(TradeApplication.user_id == user_id)
        )

    async def applications(self, user_id: int):
        result = await self.session.execute(
            self.current(
                select(TradeApplication, Fund)
                .join(Fund, Fund.id == TradeApplication.fund_id)
                .where(
                    TradeApplication.user_id == user_id,
                    TradeApplication.status == "pending",
                    TradeApplication.deleted_at.is_(None),
                )
                .order_by(TradeApplication.submitted_at, TradeApplication.id)
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def application(self, user_id: int, application_id: int):
        return (
            await self.session.execute(
                self.current(
                    select(TradeApplication).where(
                        TradeApplication.user_id == user_id, TradeApplication.id == application_id
                    )
                )
            )
        ).scalar_one_or_none()

    async def application_request(self, user_id: int, request_key: str):
        return (
            await self.session.execute(
                self.current(
                    select(TradeApplication).where(
                        TradeApplication.user_id == user_id,
                        TradeApplication.request_key == request_key,
                    )
                )
            )
        ).scalar_one_or_none()

    async def fund_by_id(self, fund_id: int):
        return await self.session.get(Fund, fund_id)

    async def by_application(self, user_id: int, application_id: int):
        return (
            await self.session.execute(
                self.current(
                    select(FundTransaction).where(
                        FundTransaction.user_id == user_id,
                        FundTransaction.application_id == application_id,
                    )
                )
            )
        ).scalar_one_or_none()

    async def automatic_pending_members(self, limit: int):
        result = await self.session.execute(
            select(TradeApplication.user_id)
            .where(
                TradeApplication.automatic_processing.is_(True),
                TradeApplication.status == "pending",
                TradeApplication.deleted_at.is_(None),
            )
            .distinct()
            .limit(limit)
        )
        return list(result.scalars())
