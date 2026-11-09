"""基金关注仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.fund import Fund
from app.models.fund_company import FundCompany, FundManager
from app.models.fund_favorite import FundFavorite
from app.models.fund_metric import FundMetric


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def codes(self, user_id: int, limit: int = 500) -> list[str]:
        """关注的基金代码，用于列表页标记星标。

        关注数通常远小于 500，一次全量拉取比"逐行查"更省往返。
        """
        stmt = (
            select(Fund.code)
            .join(FundFavorite, FundFavorite.fund_id == Fund.id)
            .where(FundFavorite.user_id == user_id, Fund.deleted_at.is_(None))
            .order_by(FundFavorite.created_at.desc(), FundFavorite.id.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(FundFavorite)
            .join(Fund, Fund.id == FundFavorite.fund_id)
            .where(FundFavorite.user_id == user_id, Fund.deleted_at.is_(None))
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def paginate(
        self, user_id: int, page: int, page_size: int, period: str = "1y"
    ) -> tuple[list[tuple[Any, ...]], int]:
        """关注列表：按关注时间倒序，附带所选区间的指标。"""
        metric = aliased(FundMetric)
        base = (
            select(Fund, metric, FundCompany.name, FundManager.name)
            .join(FundFavorite, FundFavorite.fund_id == Fund.id)
            .outerjoin(metric, and_(metric.fund_id == Fund.id, metric.period == period))
            .outerjoin(FundCompany, Fund.company_id == FundCompany.id)
            .outerjoin(FundManager, Fund.manager_id == FundManager.id)
            .where(FundFavorite.user_id == user_id, Fund.deleted_at.is_(None))
        )

        total = await self.count(user_id)
        stmt = (
            base.order_by(FundFavorite.created_at.desc(), FundFavorite.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self.session.execute(stmt)).all()
        return [tuple(r) for r in rows], total

    async def list_for_dashboard(
        self, user_id: int, period: str = "1y", limit: int = 500
    ) -> list[tuple[Any, ...]]:
        """工作台聚合用：一次取出关注记录 + 基金 + 指定区间指标。

        关注数远小于 500，一次 join 后在 Python 侧分组统计，
        比写 6 条 GROUP BY SQL 更好维护，也避免多次往返。
        """
        metric = aliased(FundMetric)
        stmt = (
            select(FundFavorite, Fund, metric)
            .join(Fund, Fund.id == FundFavorite.fund_id)
            .outerjoin(metric, and_(metric.fund_id == Fund.id, metric.period == period))
            .where(FundFavorite.user_id == user_id, Fund.deleted_at.is_(None))
            .order_by(FundFavorite.created_at.desc(), FundFavorite.id.desc())
            .limit(limit)
        )
        return [tuple(r) for r in (await self.session.execute(stmt)).all()]

    async def exists(self, user_id: int, fund_id: int) -> bool:
        stmt = select(FundFavorite.id).where(
            FundFavorite.user_id == user_id, FundFavorite.fund_id == fund_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def add(self, user_id: int, fund_id: int, note: str | None = None) -> None:
        """幂等添加：已关注时不再插入（唯一约束兜底）。"""
        if await self.exists(user_id, fund_id):
            return
        self.session.add(
            FundFavorite(
                user_id=user_id,
                fund_id=fund_id,
                note=note,
                created_at=datetime.now(),
            )
        )

    async def remove(self, user_id: int, fund_id: int) -> int:
        """硬删除：软删会占住唯一约束，导致取消后无法再次关注。"""
        result = await self.session.execute(
            delete(FundFavorite).where(
                FundFavorite.user_id == user_id, FundFavorite.fund_id == fund_id
            )
        )
        # execute() 的静态返回类型是 Result，DELETE 场景实际是 CursorResult
        return int(getattr(result, "rowcount", 0) or 0)
