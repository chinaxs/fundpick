"""基金业务逻辑：查询组装、详情、筛选项字典。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.fund_sectors import SECTOR_LABELS, SECTOR_ORDER
from app.fund_share_class import split_share_class
from app.models.fund import Fund, FundType, RiskLevel
from app.models.fund_nav import FundNav
from app.repositories.fund import FundRepository
from app.schemas.common import PageResult
from app.schemas.fund import (
    COMPARE_PERIODS,
    ComparePeriod,
    FilterOption,
    FilterOptions,
    FundCompareItem,
    FundCompareResult,
    FundDetail,
    FundListItem,
    FundQuery,
    FundSortBy,
    HoldingRead,
    HoldingsResult,
    MetricRead,
    NavPointRead,
    NavRange,
    SectorOption,
)
from app.schemas.stats import (
    DistributionBucket,
    OverviewStats,
    ReturnDistribution,
    TypeStat,
)

TYPE_LABELS: dict[str, str] = {
    FundType.STOCK: "股票型",
    FundType.HYBRID: "混合型",
    FundType.BOND: "债券型",
    FundType.INDEX: "指数型",
    FundType.QDII: "QDII",
    FundType.MONEY: "货币型",
    FundType.FOF: "FOF",
    FundType.OTHER: "其他",
}

RISK_LABELS: dict[str, str] = {
    RiskLevel.LOW: "低风险",
    RiskLevel.MID_LOW: "中低风险",
    RiskLevel.MID: "中风险",
    RiskLevel.MID_HIGH: "中高风险",
    RiskLevel.HIGH: "高风险",
}

PERIOD_LABELS: dict[str, str] = {
    "1w": "近1周",
    "1m": "近1月",
    "3m": "近3月",
    "6m": "近6月",
    "1y": "近1年",
    "2y": "近2年",
    "3y": "近3年",
    "ytd": "今年来",
    "all": "成立来",
}

SORT_LABELS: dict[str, str] = {
    FundSortBy.RETURN: "区间收益",
    FundSortBy.SHARPE: "夏普比率",
    FundSortBy.MAX_DRAWDOWN: "最大回撤",
    FundSortBy.VOLATILITY: "年化波动率",
    FundSortBy.SCALE: "规模",
    FundSortBy.NAV: "最新净值",
}


# SQL 层的读取上限：成立以来最多约 20 年 × 250 个交易日 ≈ 5000 点，
# 留出余量后由 _downsample 按需压缩到展示点数。
NAV_MAX_FETCH = 6000


def _nav_start_date(period: NavRange) -> date | None:
    days = period.days
    if days is None:
        return None
    return date.today() - timedelta(days=days)


def _downsample(points: list[NavPointRead], limit: int) -> list[NavPointRead]:
    """等距抽样，保留首尾点。

    为什么需要：成立以来可能几千个点，直接传给前端会让 JSON 膨胀到几百 KB。
    为什么用等距而不是截断：截断会丢掉早期数据，让"成立以来"名不副实。
    代价：极端单日波动可能被跳过，但折线宽度通常不足 1000px，
    2000 点已远超像素密度，视觉与统计趋势不受影响。
    """
    if limit <= 0 or len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def to_list_item(row: tuple[Any, ...]) -> FundListItem:
    """把 (Fund, FundMetric, company_name, manager_name) 映射成列表项。

    抽取出来是为了让"关注列表"复用同一套映射，避免两个接口字段口径不一致。
    """
    fund, metric, company_name, manager_name = row
    base_name, share_class = split_share_class(fund.name)
    return FundListItem(
        id=fund.id,
        code=fund.code,
        name=fund.name,
        share_class=share_class,
        base_name=base_name,
        type=fund.type,
        risk_level=fund.risk_level,
        sector=fund.sector,
        company_name=company_name,
        manager_name=manager_name,
        latest_nav=fund.latest_nav,
        latest_nav_date=fund.latest_nav_date,
        scale=fund.scale,
        fee_rate=fund.management_fee,
        return_rate=metric.return_rate if metric else None,
        max_drawdown=metric.max_drawdown if metric else None,
        volatility=metric.volatility if metric else None,
        sharpe=metric.sharpe if metric else None,
        rank=metric.rank if metric else None,
        total=metric.total if metric else None,
    )


class FundService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.funds = FundRepository(session)

    # ---------------------------------------------------------- 列表
    async def search(self, query: FundQuery) -> PageResult[FundListItem]:
        rows, total = await self.funds.search(query)
        items = [self._to_list_item(row) for row in rows]
        return PageResult(items=items, total=total, page=query.page, page_size=query.page_size)

    @staticmethod
    def _to_list_item(row: tuple[Any, ...]) -> FundListItem:
        return to_list_item(row)

    # ---------------------------------------------------------- 详情
    async def detail(self, code: str) -> FundDetail:
        row = await self.funds.get_detail(code)
        if row is None:
            raise NotFoundError("基金不存在")
        fund, company_name, manager = row
        base_name, share_class = split_share_class(fund.name)
        return FundDetail(
            id=fund.id,
            code=fund.code,
            name=fund.name,
            share_class=share_class,
            base_name=base_name,
            full_name=fund.full_name,
            type=fund.type,
            risk_level=fund.risk_level,
            sector=fund.sector,
            status=fund.status,
            company_name=company_name,
            manager_name=manager.name if manager else None,
            manager_tenure_years=manager.tenure_years if manager else None,
            manager_scale=manager.managed_scale if manager else None,
            manager_best_return=manager.best_return if manager else None,
            latest_nav=fund.latest_nav,
            latest_nav_date=fund.latest_nav_date,
            scale=fund.scale,
            fee_rate=fund.management_fee,
            custody_fee=fund.custody_fee,
            inception_date=fund.inception_date,
            is_index=fund.is_index,
            tracking_index=fund.tracking_index,
        )

    async def compare(self, codes: list[str]) -> FundCompareResult:
        """2–3 只基金横向对比。

        份额类别单独返回，避免把同一产品的 A/C 当成两个不同标的；
        区间数据缺失时 available=False，前端显示「无数据」而不是 0。
        """
        unique: list[str] = []
        for raw in codes:
            code = raw.strip()
            if code and code not in unique:
                unique.append(code)
        if len(unique) < 2:
            raise ValidationError("至少选择 2 只基金进行对比")
        if len(unique) > 3:
            raise ValidationError("最多对比 3 只基金")

        items: list[FundCompareItem] = []
        for code in unique:
            row = await self.funds.get_detail(code)
            if row is None:
                raise NotFoundError(f"基金 {code} 不存在或已下架")
            fund, company_name, manager = row
            metric_map = {metric.period: metric for metric in await self.funds.metrics(fund.id)}
            periods: list[ComparePeriod] = []
            for period, label in COMPARE_PERIODS:
                metric = metric_map.get(period)
                risk_values = (
                    (metric.max_drawdown, metric.volatility, metric.sharpe)
                    if metric is not None
                    else (None, None, None)
                )
                periods.append(
                    ComparePeriod(
                        period=period,
                        label=label,
                        return_rate=metric.return_rate if metric else None,
                        max_drawdown=metric.max_drawdown if metric else None,
                        sharpe=metric.sharpe if metric else None,
                        volatility=metric.volatility if metric else None,
                        risk_nav_date=metric.risk_nav_date if metric else None,
                        available=all(value is not None for value in risk_values),
                    )
                )
            base_name, share_class = split_share_class(fund.name)
            items.append(
                FundCompareItem(
                    code=fund.code,
                    name=fund.name,
                    share_class=share_class,
                    base_name=base_name,
                    type=fund.type,
                    type_label=TYPE_LABELS.get(fund.type, str(fund.type)),
                    risk_level=fund.risk_level,
                    risk_label=RISK_LABELS.get(fund.risk_level) if fund.risk_level else None,
                    company_name=company_name,
                    manager_name=manager.name if manager else None,
                    latest_nav=fund.latest_nav,
                    latest_nav_date=fund.latest_nav_date,
                    scale=fund.scale,
                    fee_rate=fund.management_fee,
                    custody_fee=fund.custody_fee,
                    inception_date=fund.inception_date,
                    periods=periods,
                )
            )
        return FundCompareResult(items=items)

    async def metrics(self, code: str) -> list[MetricRead]:
        from app.models.fund_metric import FundMetric
        from app.services.fund_risk import PERIOD_DAYS, SOURCE, calculate_risk

        fund = await self._require_fund(code)
        rows = await self.funds.metrics(fund.id)
        points = await self.funds.navs(fund.id, NAV_MAX_FETCH)
        by_period = {row.period: row for row in rows}
        reasons = {}
        written = False
        for period in PERIOD_DAYS:
            calculated, reason = calculate_risk(points, period, fund.inception_date)
            reasons[period] = reason
            stored = by_period.get(period)
            complete = stored is not None and all(
                value is not None
                for value in (stored.max_drawdown, stored.volatility, stored.sharpe)
            )
            if complete and stored is not None and stored.risk_source != SOURCE:
                reasons[period] = None
                continue
            if calculated is None:
                continue
            baseline = points[-1].nav_date
            if (
                stored is not None
                and stored.risk_source == SOURCE
                and stored.risk_nav_date == baseline
            ):
                continue
            statement = insert(FundMetric).values(
                fund_id=fund.id,
                period=period,
                risk_nav_date=baseline,
                risk_source=SOURCE,
                **calculated,
            )
            await self.session.execute(
                statement.on_duplicate_key_update(
                    risk_nav_date=baseline,
                    risk_source=SOURCE,
                    **calculated,
                )
            )
            written = True
        if written:
            await self.session.commit()
            self.session.expire_all()
            fund = await self._require_fund(code)
            rows = await self.funds.metrics(fund.id)
        by_period = {row.period: row for row in rows}
        for period in PERIOD_DAYS:
            if period not in by_period:
                rows.append(FundMetric(fund_id=fund.id, period=period))
        return [
            MetricRead(
                period=m.period,
                return_rate=m.return_rate,
                annual_return=m.annual_return,
                max_drawdown=m.max_drawdown,
                volatility=m.volatility,
                sharpe=m.sharpe,
                risk_nav_date=m.risk_nav_date,
                risk_source=m.risk_source,
                risk_reason=reasons.get(m.period)
                if not all(value is not None for value in (m.max_drawdown, m.volatility, m.sharpe))
                else None,
                risk_coverage=sum(
                    value is not None for value in (m.max_drawdown, m.volatility, m.sharpe)
                ),
                risk_stale=m.risk_nav_date is None
                or fund.latest_nav_date is None
                or m.risk_nav_date != fund.latest_nav_date,
                rank=m.rank,
                total=m.total,
            )
            for m in rows
        ]

    async def ensure_navs(
        self, code: str, period: NavRange = NavRange.Y1, limit: int = 2000
    ) -> list[NavPointRead]:
        """Refresh even when a local series exists; failures retain dated cached values."""
        from app.services.fund_data import refresh_data

        fund = await self._require_fund(code)
        await refresh_data(self.session, fund, "navs")
        # A newer official snapshot remains useful when the history source is delayed.
        # Do not infer its daily return from unit NAV (cash dividends can change it).
        if fund.latest_nav_date and fund.latest_nav and fund.latest_nav > 0:
            latest = await self.funds.navs(fund.id, 1)
            if not latest or latest[-1].nav_date < fund.latest_nav_date:
                statement = insert(FundNav).values(
                    fund_id=fund.id,
                    nav_date=fund.latest_nav_date,
                    unit_nav=fund.latest_nav,
                    daily_return=None,
                )
                await self.session.execute(
                    statement.on_duplicate_key_update(
                        unit_nav=statement.inserted.unit_nav,
                    )
                )
                await self.session.commit()
        rows = await self.funds.navs(fund.id, NAV_MAX_FETCH, start_date=_nav_start_date(period))
        return _downsample(self._to_nav_reads(rows), limit)

    @staticmethod
    def _to_nav_reads(rows: list[FundNav]) -> list[NavPointRead]:
        return [
            NavPointRead(nav_date=n.nav_date, unit_nav=n.unit_nav, daily_return=n.daily_return)
            for n in rows
        ]

    # ---------------------------------------------------------- 持仓
    async def holdings(self, code: str, quarter: str | None = None) -> HoldingsResult:
        """季度重仓股按需复查，已有季度也会更新；上游失败保留已披露数据。

        持仓是季报数据（一个季度约 4 万行全市场），预拉不划算，
        按需补齐最经济。
        """
        from app.services.fund_data import refresh_data

        fund = await self._require_fund(code)
        await refresh_data(self.session, fund, "holdings")
        quarters = await self.funds.holding_quarters(fund.id)

        target = quarter if quarter in quarters else (quarters[0] if quarters else None)
        if target is None:
            return HoldingsResult(quarters=quarters, quarter=None, items=[], total_ratio=None)

        holding_rows = await self.funds.holdings(fund.id, target)
        items = [
            HoldingRead(
                quarter=h.quarter,
                stock_code=h.stock_code,
                stock_name=h.stock_name,
                rank=h.rank,
                ratio=float(h.ratio) if h.ratio is not None else None,
                shares=float(h.shares) if h.shares is not None else None,
                market_value=float(h.market_value) if h.market_value is not None else None,
            )
            for h in holding_rows
        ]
        top10 = [i for i in items if (i.rank or 99) <= 10]
        total_ratio = round(sum(i.ratio or 0 for i in top10), 2) if top10 else None
        return HoldingsResult(
            quarters=quarters, quarter=target, items=items, total_ratio=total_ratio
        )

    async def navs(
        self, code: str, period: NavRange = NavRange.Y1, limit: int = 2000
    ) -> list[NavPointRead]:
        fund = await self._require_fund(code)
        rows = await self.funds.navs(fund.id, NAV_MAX_FETCH, start_date=_nav_start_date(period))
        return _downsample(self._to_nav_reads(rows), limit)

    async def _require_fund(self, code: str) -> Fund:
        fund = await self.funds.get_by_code(code)
        if fund is None:
            raise NotFoundError("基金不存在")
        return fund

    # ---------------------------------------------------------- 字典
    async def filter_options(self) -> FilterOptions:
        companies = await self.funds.companies()
        sector_counts = await self.funds.sector_distribution()
        return FilterOptions(
            types=[FilterOption(value=k, label=v) for k, v in TYPE_LABELS.items()],
            risk_levels=[FilterOption(value=k, label=v) for k, v in RISK_LABELS.items()],
            sectors=[
                SectorOption(value=key, label=SECTOR_LABELS[key], count=sector_counts[key])
                for key in SECTOR_ORDER
                if sector_counts.get(key)
            ],
            companies=[FilterOption(value=c.id, label=c.name) for c in companies],
            periods=[FilterOption(value=k, label=v) for k, v in PERIOD_LABELS.items()],
            sort_fields=[FilterOption(value=k, label=v) for k, v in SORT_LABELS.items()],
        )

    # ---------------------------------------------------------- 统计
    async def overview_stats(self) -> OverviewStats:
        """首页概览：数量、公司数、类型分布与各类型平均收益。"""
        rows = await self.funds.type_distribution()
        total = sum(count for _, count, _ in rows)
        return OverviewStats(
            total_funds=total,
            total_companies=await self.funds.company_count(),
            latest_nav_date=await self.funds.latest_nav_date(),
            type_distribution=[
                TypeStat(
                    type=fund_type,
                    label=TYPE_LABELS.get(fund_type, fund_type),
                    count=count,
                    avg_return=round(avg, 2) if avg is not None else None,
                )
                for fund_type, count, avg in rows
            ],
        )

    async def return_distribution(self, period: str = "1y") -> ReturnDistribution:
        rows = await self.funds.return_buckets(period)
        mapping = dict(rows)
        # 固定顺序输出，前端画图不用再排序
        order = ["<-30%", "-30~-20%", "-20~-10%", "-10~0%", "0~10%", "10~20%", "20~50%", ">50%"]
        buckets = [DistributionBucket(label=label, count=mapping.get(label, 0)) for label in order]
        return ReturnDistribution(
            period=period, total=sum(b.count for b in buckets), buckets=buckets
        )

    async def overview(self) -> dict[str, int]:
        """首页概览：基金总数。"""
        return {"total_funds": await self.funds.count_all()}
