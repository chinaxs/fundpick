"""根据有效交易与公司行为生成持仓、累计收益及待核对旧记录。

持仓不再读流水行上的余额快照，而是用 `services/ledger.replay` 按日期重放：
买入/卖出/分红/再投/拆分/转换都在同一条时间线上计算，避免"补录拆分后
核对页与卖出校验各说各话"。
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.repositories.transaction import TransactionRepository
from app.schemas.portfolio import HoldingRead, PortfolioRead, PortfolioSummary
from app.services.ledger import replay
from app.services.portal_position import PositionService
from app.services.portfolio_math import ZERO, money


class PortfolioService:
    def __init__(self, session: AsyncSession):
        self.repo = TransactionRepository(session)
        self.legacy = PositionService(session)

    async def held_codes(self, user_id: int) -> list[str]:
        """基金展示页共用的持仓标识：按重放后的份额判断，拆分后仍能识别。

        只出现在公司行为里的基金（例如本月才从别的基金转换进来）也要算持仓，
        否则列表会漏掉它，用户点进详情页才发现自己"持有"。
        """
        rows = await self.repo.rows(user_id)
        flows = await self.repo.flows(user_id)
        grouped: dict[int, list] = defaultdict(list)
        codes: dict[int, str] = {}
        for row, fund in rows:
            if row.status != "confirmed":
                continue
            grouped[fund.id].append(row)
            codes[fund.id] = fund.code
        by_fund: dict[int, list] = defaultdict(list)
        for flow in flows:
            by_fund[flow.fund_id].append(flow)
        flow_only = set(by_fund) - set(grouped)
        if flow_only:
            for fund in await self.repo.funds_by_ids(sorted(flow_only)):
                codes[fund.id] = fund.code
                grouped.setdefault(fund.id, [])
        held = [
            codes[fund_id]
            for fund_id, items in grouped.items()
            if replay(items, by_fund.get(fund_id, [])).shares > 0
        ]
        return sorted(held)

    async def overview(self, user_id: int) -> PortfolioRead:
        """保留清仓基金已实现收益；缺失任一最新净值则不汇总总估值。"""
        rows = await self.repo.rows(user_id)
        flows = await self.repo.flows(user_id)
        grouped: dict[int, list] = defaultdict(list)
        funds: dict[int, Fund] = {}
        for row, fund in rows:
            funds[fund.id] = fund
            if row.status != "confirmed":
                continue
            grouped[fund.id].append((row, fund))
        flows_by_fund: dict[int, list] = defaultdict(list)
        for flow in flows:
            flows_by_fund[flow.fund_id].append(flow)
        # 只有公司行为（例如从别处转入）的基金也要出现在持仓里
        flow_only = {flow.fund_id for flow in flows} - set(grouped)
        if flow_only:
            for fund in await self.repo.funds_by_ids(sorted(flow_only)):
                funds[fund.id] = fund
                grouped.setdefault(fund.id, [])

        holdings = [
            self._holding(items, flows_by_fund.get(fund_id, []), funds[fund_id])
            for fund_id, items in grouped.items()
        ]
        holdings.sort(key=lambda h: (h.shares == 0, -h.remaining_cost, h.code))
        legacy, _ = await self.legacy.overview(user_id)
        legacy.sort(key=lambda item: (item.bought_at, item.id))
        summary = self._summary(holdings)
        summary.legacy_count = len(legacy)
        summary.transaction_count = sum(len(items) for items in grouped.values())
        summary.calculated_count = sum(
            1 for items in grouped.values() for row, _ in items if row.record_source == "calculated"
        )
        summary.estimated_count = sum(
            1 for items in grouped.values() for row, _ in items if row.record_source == "estimated"
        )
        summary.pending_count = len(await self.repo.applications(user_id))
        return PortfolioRead(holdings=holdings, summary=summary, legacy_positions=legacy)

    @staticmethod
    def _holding(items: list, flows: list, fund: Fund) -> HoldingRead:
        rows = [item[0] for item in items]
        state = replay(rows, flows)
        # 最新净值必须晚于**最后一笔事件**（含拆分/再投/转换）才可用于估值：
        # 拆分前的净值乘上拆分后的份额会凭空造出一笔涨幅。
        days = [row.confirmed_on for row in rows] + [flow.effective_on for flow in flows]
        last_day = max(days) if days else None
        latest_nav = fund.latest_nav
        valid_nav = (
            latest_nav is not None
            and latest_nav > 0
            and fund.latest_nav_date is not None
            and (last_day is None or fund.latest_nav_date >= last_day)
        )
        # 缺净值只表示"暂时估不出市值"，持仓本身仍然可读，不能让整个组合 500
        value = money(state.shares * latest_nav) if valid_nav and latest_nav else None
        if state.shares == ZERO:
            value = ZERO
        profit = value - state.cost if value is not None else None
        return HoldingRead(
            estimated_count=sum(1 for row in rows if row.record_source == "estimated"),
            code=fund.code,
            name=fund.name,
            shares=float(state.shares),
            remaining_cost=float(state.cost),
            average_cost=float(state.cost / state.shares) if state.shares else None,
            latest_nav=float(fund.latest_nav) if fund.latest_nav is not None else None,
            latest_nav_date=fund.latest_nav_date,
            market_value=float(value) if value is not None else None,
            holding_profit=float(profit) if profit is not None else None,
            realized_profit=float(state.realized),
            dividends=float(state.dividends),
            total_profit=float(profit + state.realized) if profit is not None else None,
            total_buy_amount=float(state.bought),
            total_sell_amount=float(state.sold),
            fees=float(state.fees),
            last_confirmed_on=last_day,
        )

    @staticmethod
    def _summary(holdings: list[HoldingRead]) -> PortfolioSummary:
        active = [item for item in holdings if item.shares > 0]
        valued = [item for item in active if item.market_value is not None]

        def total(key: str) -> float:
            return float(money(sum((Decimal(str(getattr(h, key))) for h in holdings), ZERO)))

        cost, realized = total("remaining_cost"), total("realized_profit")
        complete = len(active) == len(valued)
        value = (
            float(money(sum((Decimal(str(h.market_value)) for h in valued), ZERO)))
            if complete
            else None
        )
        profit = (
            float(money(Decimal(str(value)) - Decimal(str(cost)))) if value is not None else None
        )
        total_return = (
            float(money(Decimal(str(profit)) + Decimal(str(realized))))
            if profit is not None
            else None
        )
        return PortfolioSummary(
            count=len(active),
            total_amount=cost,
            valued_count=len(valued),
            total_market_value=value,
            total_profit=profit,
            profit_rate=round(profit / cost * 100, 2) if profit is not None and cost else None,
            realized_profit=realized,
            total_dividends=total("dividends"),
            total_return=total_return,
            total_buy_amount=total("total_buy_amount"),
            total_sell_amount=total("total_sell_amount"),
            fees=total("fees"),
        )
