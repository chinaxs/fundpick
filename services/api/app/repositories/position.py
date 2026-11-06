"""模拟持仓仓储：按会员隔离的 CRUD + 明细 join。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.models.fund_position import FundPosition


class PositionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned(self, user_id: int, position_id: int) -> FundPosition | None:
        """只取本人且未删除的持仓，杜绝越权改别人的记录。"""
        stmt = select(FundPosition).where(
            FundPosition.id == position_id,
            FundPosition.user_id == user_id,
            FundPosition.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_with_fund(
        self, user_id: int, limit: int = 500
    ) -> list[tuple[Any, ...]]:
        stmt = (
            select(FundPosition, Fund)
            .join(Fund, Fund.id == FundPosition.fund_id)
            .where(
                FundPosition.user_id == user_id,
                FundPosition.deleted_at.is_(None),
                Fund.deleted_at.is_(None),
            )
            .order_by(FundPosition.bought_at.desc(), FundPosition.id.desc())
            .limit(limit)
        )
        return [tuple(r) for r in (await self.session.execute(stmt)).all()]

    async def find_fund_id(self, code: str) -> int | None:
        stmt = select(Fund.id).where(Fund.code == code, Fund.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(
        self,
        user_id: int,
        fund_id: int,
        amount: float,
        cost_nav: float,
        bought_at: date,
        note: str | None,
    ) -> FundPosition:
        position = FundPosition(
            user_id=user_id,
            fund_id=fund_id,
            amount=amount,
            cost_nav=cost_nav,
            bought_at=bought_at,
            note=note,
        )
        self.session.add(position)
        await self.session.commit()
        await self.session.refresh(position)
        return position

    async def update(self, position: FundPosition, **data: Any) -> FundPosition:
        for key, value in data.items():
            setattr(position, key, value)
        position.updated_at = datetime.now()
        await self.session.commit()
        await self.session.refresh(position)
        return position

    async def remove(self, position: FundPosition) -> None:
        """硬删除：模拟持仓允许反复增删，软删会留下无用记录。"""
        await self.session.delete(position)
        await self.session.commit()
