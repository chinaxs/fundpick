"""模拟持仓服务：录入只收金额，份额与盈亏全部由服务端计算。

计算口径：
    shares       = amount / cost_nav          （买入时净值折算份额）
    market_value = shares * latest_nav       （按最新单位净值估值）
    profit       = market_value - amount
    profit_rate  = profit / amount * 100

`cost_nav` 是用户录入的买入时净值，不是当前净值；最新净值取 funds.latest_nav
冗余列（采集任务写入），因此估值不依赖净值历史表，也不涉及真实交易。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.fund import Fund
from app.models.fund_position import FundPosition
from app.repositories.position import PositionRepository
from app.schemas.portal_me import (
    PositionCreateRequest,
    PositionItem,
    PositionSummary,
    PositionUpdateRequest,
)


def _f(value: Decimal | float | int | None) -> float:
    return float(value) if value is not None else 0.0


class PositionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.positions = PositionRepository(session)

    # ---------------------------------------------------------- 计算
    @staticmethod
    def _to_item(position: FundPosition, fund: Fund) -> PositionItem:
        amount = _f(position.amount)
        cost_nav = _f(position.cost_nav)
        shares = amount / cost_nav if cost_nav > 0 else 0.0
        latest_nav = float(fund.latest_nav) if fund.latest_nav is not None else None
        market_value = round(shares * latest_nav, 2) if latest_nav is not None else None
        profit = round(market_value - amount, 2) if market_value is not None else None
        profit_rate = round(profit / amount * 100, 2) if profit is not None and amount else None

        return PositionItem(
            id=position.id,
            code=fund.code,
            name=fund.name,
            type=str(fund.type),
            sector=fund.sector,
            amount=round(amount, 2),
            cost_nav=round(cost_nav, 4),
            bought_at=position.bought_at,
            note=position.note,
            shares=round(shares, 2),
            latest_nav=latest_nav,
            latest_nav_date=fund.latest_nav_date,
            market_value=market_value,
            profit=profit,
            profit_rate=profit_rate,
            created_at=position.created_at,
        )

    @staticmethod
    def _summarize(items: list[PositionItem]) -> PositionSummary:
        total_amount = sum(i.amount for i in items)
        valued = [i for i in items if i.market_value is not None]
        if not valued:
            return PositionSummary(count=len(items), total_amount=round(total_amount, 2))
        total_value = sum(i.market_value or 0 for i in valued)
        total_profit = round(total_value - total_amount, 2)
        return PositionSummary(
            count=len(items),
            total_amount=round(total_amount, 2),
            total_market_value=round(total_value, 2),
            total_profit=total_profit,
            profit_rate=round(total_profit / total_amount * 100, 2) if total_amount else None,
            valued_count=len(valued),
        )

    async def overview(self, user_id: int) -> tuple[list[PositionItem], PositionSummary]:
        rows = await self.positions.list_with_fund(user_id)
        items = [self._to_item(pos, fund) for pos, fund in rows]
        return items, self._summarize(items)

    # ---------------------------------------------------------- CRUD
    async def create(self, user_id: int, payload: PositionCreateRequest) -> PositionItem:
        fund_id = await self.positions.find_fund_id(payload.code)
        if fund_id is None:
            raise NotFoundError("基金代码不存在")
        if payload.cost_nav <= 0 or payload.amount <= 0:
            raise ValidationError("金额与买入净值必须大于 0")

        position = await self.positions.add(
            user_id=user_id,
            fund_id=fund_id,
            amount=Decimal(str(payload.amount)),
            cost_nav=Decimal(str(payload.cost_nav)),
            bought_at=payload.bought_at or date.today(),
            note=payload.note or None,
        )
        fund = await self.session.get(Fund, fund_id)
        if fund is None:  # pragma: no cover - 外键刚校验过
            raise NotFoundError("基金不存在")
        return self._to_item(position, fund)

    async def update(
        self, user_id: int, position_id: int, payload: PositionUpdateRequest
    ) -> PositionItem:
        position = await self.positions.get_owned(user_id, position_id)
        if position is None:
            raise NotFoundError("持仓记录不存在")

        data = payload.model_dump(exclude_unset=True)
        if "amount" in data and data["amount"] is not None:
            data["amount"] = Decimal(str(data["amount"]))
        if "cost_nav" in data and data["cost_nav"] is not None:
            data["cost_nav"] = Decimal(str(data["cost_nav"]))
        if "note" in data:
            data["note"] = data["note"] or None
        data = {k: v for k, v in data.items() if v is not None}

        await self.positions.update(position, **data)
        fund = await self.session.get(Fund, position.fund_id)
        if fund is None:  # pragma: no cover
            raise NotFoundError("基金不存在")
        return self._to_item(position, fund)

    async def delete(self, user_id: int, position_id: int) -> None:
        position = await self.positions.get_owned(user_id, position_id)
        if position is None:
            raise NotFoundError("持仓记录不存在")
        await self.positions.remove(position)
