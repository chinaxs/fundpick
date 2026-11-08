"""模拟持仓服务：用户只录金额与日期，净值/份额/盈亏全部由服务端计算。

净值获取（用户不需要懂净值）：
    按买入日期查 fund_navs 中"当天或之前最近一个交易日"的单位净值；
    非交易日自然落到上一交易日。本地没有该日期之前的历史净值时，
    回退到 funds.latest_nav 并在 nav_source 标注 latest，如实告诉用户。

计算口径：
    shares       = amount / cost_nav          （自动折算份额）
    market_value = shares * latest_nav       （按最新单位净值估值）
    profit       = market_value - amount
    profit_rate  = profit / amount * 100
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

    # ---------------------------------------------------------- 净值解析
    async def _resolve_nav(self, fund: Fund, bought_at: date) -> tuple[Decimal, date | None, str]:
        """返回 (单位净值, 净值日期, 来源)。用户完全不需要手填净值。"""
        row = await self.positions.nav_on_or_before(fund.id, bought_at)
        if row and row[0] and row[0] > 0:
            return row[0], row[1], "history"
        if fund.latest_nav is not None and fund.latest_nav > 0:
            return fund.latest_nav, fund.latest_nav_date, "latest"
        raise ValidationError("该基金暂无净值数据，无法自动折算份额，请稍后再试")

    @staticmethod
    def _validate_buy_date(fund: Fund, bought_at: date) -> None:
        if bought_at > date.today():
            raise ValidationError("买入日期不能晚于今天")
        if fund.inception_date and bought_at < fund.inception_date:
            raise ValidationError("买入日期早于该基金成立日，请检查日期")

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
            cost_nav_date=position.cost_nav_date,
            nav_source=position.nav_source,
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
        # 缺失净值不等于市值为零；只有全部记录可估值时才给出组合总收益。
        if not valued or len(valued) != len(items):
            return PositionSummary(
                count=len(items), total_amount=round(total_amount, 2), valued_count=len(valued)
            )
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
        fund = await self.positions.find_fund(payload.code)
        if fund is None:
            raise NotFoundError("基金代码不存在")
        if payload.amount <= 0:
            raise ValidationError("买入金额必须大于 0")

        bought_at = payload.bought_at or date.today()
        self._validate_buy_date(fund, bought_at)
        cost_nav, nav_date, nav_source = await self._resolve_nav(fund, bought_at)

        position = await self.positions.add(
            user_id=user_id,
            fund_id=fund.id,
            amount=Decimal(str(payload.amount)),
            cost_nav=cost_nav,
            cost_nav_date=nav_date,
            nav_source=nav_source,
            bought_at=bought_at,
            note=payload.note or None,
        )
        return self._to_item(position, fund)

    async def update(
        self, user_id: int, position_id: int, payload: PositionUpdateRequest
    ) -> PositionItem:
        position = await self.positions.get_owned(user_id, position_id)
        if position is None:
            raise NotFoundError("持仓记录不存在")
        fund = await self.session.get(Fund, position.fund_id)
        if fund is None:  # pragma: no cover - 外键约束保证存在
            raise NotFoundError("基金不存在")

        data = payload.model_dump(exclude_unset=True)
        if "amount" in data and data["amount"] is not None:
            data["amount"] = Decimal(str(data["amount"]))
        if "note" in data:
            data["note"] = data["note"] or None
        data = {k: v for k, v in data.items() if v is not None}

        # 日期变化必须重算净值；迁移前的老记录缺 cost_nav_date 时顺带补齐
        if "bought_at" in data or position.cost_nav_date is None:
            bought_at = data.get("bought_at") or position.bought_at
            self._validate_buy_date(fund, bought_at)
            nav, nav_date, nav_source = await self._resolve_nav(fund, bought_at)
            data.update(cost_nav=nav, cost_nav_date=nav_date, nav_source=nav_source)

        await self.positions.update(position, **data)
        return self._to_item(position, fund)

    async def delete(self, user_id: int, position_id: int) -> None:
        position = await self.positions.get_owned(user_id, position_id)
        if position is None:
            raise NotFoundError("持仓记录不存在")
        await self.positions.remove(position)
