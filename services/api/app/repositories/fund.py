"""基金仓储：把"筛选 + 排序 + 分页"收敛成一条 SQL。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import aliased

from app.fund_search import search_tokens, sector_code_for
from app.models.fund import Fund
from app.models.fund_company import FundCompany, FundManager
from app.models.fund_holding import FundHolding
from app.models.fund_metric import FundMetric
from app.models.fund_nav import FundNav
from app.repositories.base import BaseRepository
from app.schemas.fund import FundQuery, FundSortBy, SortOrder


class FundRepository(BaseRepository[Fund]):
    model = Fund

    # ---------------------------------------------------------- 内部
    @staticmethod
    def _keyword_clause(token: str) -> Any:
        """单个关键词的命中条件。

        一次覆盖用户可能的四种输入：
        代码（000001）、名称片段（华夏成长）、拼音/首字母（huaxia / hxcz）、
        公司名（易方达）、主题词（半导体 → 映射成板块 key）。

        代价是全表扫描：`%x%` 用不到索引。28k 行的规模下约几十毫秒，
        比"精确前缀匹配"慢，但换来的是"想怎么输都能搜到"。
        """
        like = f"%{token}%"
        latin = token.lower()
        conditions = [
            Fund.code.like(like),
            Fund.name.like(like),
            Fund.full_name.like(like),
            Fund.name_pinyin.like(f"%{latin}%"),
            Fund.name_initials.like(f"%{latin}%"),
            Fund.company_id.in_(select(FundCompany.id).where(FundCompany.name.like(like))),
        ]
        sector = sector_code_for(token)
        if sector:
            conditions.append(Fund.sector == sector)
        return or_(*conditions)

    @classmethod
    def _apply_filters(cls, stmt: Select[Any], query: FundQuery) -> Select[Any]:
        stmt = stmt.where(Fund.deleted_at.is_(None))
        for token in search_tokens(query.keyword):
            stmt = stmt.where(cls._keyword_clause(token))
        if query.type:
            stmt = stmt.where(Fund.type == query.type)
        if query.risk_level:
            stmt = stmt.where(Fund.risk_level == query.risk_level)
        if query.sector:
            stmt = stmt.where(Fund.sector == query.sector)
        if query.company_id:
            stmt = stmt.where(Fund.company_id == query.company_id)
        return stmt

    @staticmethod
    def _order_clause(metric: Any, query: FundQuery) -> Any:
        """排序统一把 NULL 放最后，避免"没数据的基金"占据榜首。"""
        mapping = {
            FundSortBy.RETURN: metric.return_rate,
            FundSortBy.SHARPE: metric.sharpe,
            FundSortBy.MAX_DRAWDOWN: metric.max_drawdown,
            FundSortBy.VOLATILITY: metric.volatility,
            FundSortBy.SCALE: Fund.scale,
            FundSortBy.NAV: Fund.latest_nav,
        }
        column = mapping[query.sort_by]
        if query.sort_order == SortOrder.ASC:
            return (column.is_(None), column.asc())
        return (column.is_(None), column.desc())

    # ---------------------------------------------------------- 查询
    async def search(self, query: FundQuery) -> tuple[list[tuple[Any, ...]], int]:
        metric = aliased(FundMetric)

        base = (
            select(Fund, metric, FundCompany.name, FundManager.name)
            .outerjoin(metric, and_(metric.fund_id == Fund.id, metric.period == query.period))
            .outerjoin(FundCompany, Fund.company_id == FundCompany.id)
            .outerjoin(FundManager, Fund.manager_id == FundManager.id)
        )
        base = self._apply_filters(base, query)

        count_stmt = self._apply_filters(select(func.count()).select_from(Fund), query)
        total = int((await self.session.execute(count_stmt)).scalar_one())

        offset = (query.page - 1) * query.page_size
        page_stmt = (
            base.order_by(*self._order_clause(metric, query), Fund.id)
            .limit(query.page_size)
            .offset(offset)
        )
        rows = (await self.session.execute(page_stmt)).all()
        return [tuple(r) for r in rows], total

    async def get_by_code(self, code: str) -> Fund | None:
        return await self.get_by(code=code)

    async def get_detail(self, code: str) -> tuple[Fund, str | None, FundManager | None] | None:
        """详情页需要公司名与经理信息，一次 join 取回，避免异步下懒加载报错。"""
        stmt = (
            select(Fund, FundCompany.name, FundManager)
            .outerjoin(FundCompany, Fund.company_id == FundCompany.id)
            .outerjoin(FundManager, Fund.manager_id == FundManager.id)
            .where(Fund.code == code, Fund.deleted_at.is_(None))
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        return row[0], row[1], row[2]

    async def metrics(self, fund_id: int) -> list[FundMetric]:
        stmt = select(FundMetric).where(FundMetric.fund_id == fund_id).order_by(FundMetric.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def navs(
        self, fund_id: int, limit: int = 2000, *, start_date: date | None = None
    ) -> list[FundNav]:
        """取净值序列（倒序取再反转，避免大表正序扫描）。

        start_date 为 None 表示"成立以来"，此时不限制跨度，
        仅用 limit 兜住极端情况（由 service 层做等距抽样，不会丢掉首尾）。
        """
        stmt = select(FundNav).where(FundNav.fund_id == fund_id)
        if start_date is not None:
            stmt = stmt.where(FundNav.nav_date >= start_date)
        stmt = stmt.order_by(FundNav.nav_date.desc()).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()
        return rows

    async def holdings(self, fund_id: int, quarter: str | None = None) -> list[FundHolding]:
        """季度重仓股，按占比降序。quarter 为 None 时取最新披露季度。"""
        stmt = select(FundHolding).where(FundHolding.fund_id == fund_id)
        if quarter is None:
            latest = (
                select(func.max(FundHolding.quarter))
                .where(FundHolding.fund_id == fund_id)
                .scalar_subquery()
            )
            stmt = stmt.where(FundHolding.quarter == latest)
        else:
            stmt = stmt.where(FundHolding.quarter == quarter)
        stmt = stmt.order_by(FundHolding.rank)
        return list((await self.session.execute(stmt)).scalars().all())

    async def holding_quarters(self, fund_id: int) -> list[str]:
        """该基金已披露持仓的季度，倒序。"""
        stmt = (
            select(FundHolding.quarter)
            .where(FundHolding.fund_id == fund_id)
            .distinct()
            .order_by(FundHolding.quarter.desc())
        )
        return [row[0] for row in (await self.session.execute(stmt)).all()]

    async def companies(self) -> list[FundCompany]:
        stmt = select(FundCompany).order_by(FundCompany.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def sector_distribution(self) -> dict[str, int]:
        """各主题板块的基金数量（供筛选项字典展示热度）。"""
        stmt = (
            select(Fund.sector, func.count(Fund.id))
            .where(Fund.deleted_at.is_(None), Fund.sector.is_not(None))
            .group_by(Fund.sector)
        )
        rows = (await self.session.execute(stmt)).all()
        return {str(sector): int(count) for sector, count in rows if sector is not None}

    async def type_distribution(self, period: str = "1y") -> list[tuple[str, int, float | None]]:
        """按基金类型统计数量与区间平均收益。"""
        metric = aliased(FundMetric)
        stmt = (
            select(
                Fund.type,
                func.count(Fund.id),
                func.avg(metric.return_rate),
            )
            .outerjoin(metric, and_(metric.fund_id == Fund.id, metric.period == period))
            .where(Fund.deleted_at.is_(None), Fund.latest_nav.is_not(None))
            .group_by(Fund.type)
            .order_by(func.count(Fund.id).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            (row[0], int(row[1]), float(row[2]) if row[2] is not None else None) for row in rows
        ]

    async def return_buckets(self, period: str = "1y") -> list[tuple[str, int]]:
        """区间收益分布，用于首页直方图。

        分桶放在 SQL 里做，避免把 1.8 万条收益拉到应用层再分组。
        """
        from sqlalchemy import case, literal

        rate = FundMetric.return_rate
        bucket = case(
            (rate < -30, literal("<-30%")),
            (rate < -20, literal("-30~-20%")),
            (rate < -10, literal("-20~-10%")),
            (rate < 0, literal("-10~0%")),
            (rate < 10, literal("0~10%")),
            (rate < 20, literal("10~20%")),
            (rate < 50, literal("20~50%")),
            else_=literal(">50%"),
        ).label("bucket")

        stmt = (
            select(bucket, func.count())
            .where(FundMetric.period == period, FundMetric.return_rate.is_not(None))
            .group_by(bucket)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(str(row[0]), int(row[1])) for row in rows]

    async def company_count(self) -> int:
        stmt = select(func.count()).select_from(FundCompany)
        return int((await self.session.execute(stmt)).scalar_one())

    async def latest_nav_date(self) -> date | None:
        stmt = select(func.max(Fund.latest_nav_date))
        return (await self.session.execute(stmt)).scalar_one()

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(Fund).where(Fund.deleted_at.is_(None))
        return int((await self.session.execute(stmt)).scalar_one())
