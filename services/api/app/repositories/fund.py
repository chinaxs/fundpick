"""基金仓储：把"筛选 + 排序 + 分页"收敛成一条 SQL。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import aliased

from app.models.fund import Fund
from app.models.fund_company import FundCompany, FundManager
from app.models.fund_metric import FundMetric
from app.models.fund_nav import FundNav
from app.repositories.base import BaseRepository
from app.schemas.fund import FundQuery, FundSortBy, SortOrder


class FundRepository(BaseRepository[Fund]):
    model = Fund

    # ---------------------------------------------------------- 内部
    @staticmethod
    def _apply_filters(stmt: Select[Any], query: FundQuery) -> Select[Any]:
        stmt = stmt.where(Fund.deleted_at.is_(None))
        if query.keyword:
            like = f"%{query.keyword}%"
            stmt = stmt.where(or_(Fund.code.like(like), Fund.name.like(like)))
        if query.type:
            stmt = stmt.where(Fund.type == query.type)
        if query.risk_level:
            stmt = stmt.where(Fund.risk_level == query.risk_level)
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

    async def navs(self, fund_id: int, limit: int = 500) -> list[FundNav]:
        """取最近 N 个净值点（倒序取再反转，避免大表正序扫描）。"""
        stmt = (
            select(FundNav)
            .where(FundNav.fund_id == fund_id)
            .order_by(FundNav.nav_date.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()
        return rows

    async def companies(self) -> list[FundCompany]:
        stmt = select(FundCompany).order_by(FundCompany.name)
        return list((await self.session.execute(stmt)).scalars().all())

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
