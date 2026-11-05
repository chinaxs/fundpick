"""后台运营统计的查询集合。

这里集中所有"给管理端看的聚合查询"，避免它们散落到各个业务仓储里。
全部是只读统计，不含业务规则。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, ArticleStatus
from app.models.audit_log import AuditLog
from app.models.fund import Fund
from app.models.fund_company import FundCompany, FundManager
from app.models.fund_favorite import FundFavorite
from app.models.fund_metric import FundMetric
from app.models.fund_nav import FundNav
from app.models.user import User


class AdminStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _scalar(self, stmt: Any) -> int:
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def fund_total(self) -> int:
        return await self._scalar(
            select(func.count()).select_from(Fund).where(Fund.deleted_at.is_(None))
        )

    async def company_total(self) -> int:
        return await self._scalar(select(func.count()).select_from(FundCompany))

    async def manager_total(self) -> int:
        return await self._scalar(select(func.count()).select_from(FundManager))

    async def fund_field_coverage(self) -> dict[str, int]:
        """基金主数据里各关键字段的覆盖数量。"""
        total = await self.fund_total()
        row = (
            await self.session.execute(
                select(
                    func.count(func.distinct(FundNav.fund_id)),
                ).select_from(FundNav)
            )
        ).scalar_one()

        # 用 COUNT(列) 而不是 SUM(列 IS NOT NULL)：后者在 SQLAlchemy 里
        # 被推断为布尔，驱动会把结果转成 True/False，int(True) == 1，
        # 覆盖率会全部显示 0%。COUNT(col) 天然跳过 NULL。
        fields = await self.session.execute(
            select(
                func.count(Fund.latest_nav),
                func.count(Fund.scale),
                func.count(Fund.inception_date),
                func.count(Fund.manager_id),
                func.count(Fund.company_id),
            )
            .select_from(Fund)
            .where(Fund.deleted_at.is_(None))
        )
        latest_nav, scale, inception, manager, company = fields.one()

        metric_funds = (
            await self.session.execute(
                select(func.count(func.distinct(FundMetric.fund_id))).where(
                    FundMetric.period == "1y"
                )
            )
        ).scalar_one()

        return {
            "total": total,
            "nav": int(row or 0),
            "metric": int(metric_funds or 0),
            "latest_nav": int(latest_nav or 0),
            "scale": int(scale or 0),
            "inception_date": int(inception or 0),
            "manager": int(manager or 0),
            "company": int(company or 0),
        }

    async def nav_stats(self) -> tuple[int, date | None]:
        rows = await self._scalar(select(func.count()).select_from(FundNav))
        latest: date | None = (
            await self.session.execute(select(func.max(FundNav.nav_date)))
        ).scalar_one()
        return rows, latest

    async def user_counts(self) -> tuple[int, int, int]:
        """总数、后台账号数、近 7 天新增。"""
        total = await self._scalar(select(func.count()).select_from(User))
        staff = await self._scalar(
            select(func.count()).select_from(User).where(User.is_staff.is_(True))
        )
        since = datetime.now() - timedelta(days=7)
        new_7d = await self._scalar(
            select(func.count()).select_from(User).where(User.created_at >= since)
        )
        return total, staff, new_7d

    async def article_counts(self) -> tuple[int, int]:
        total = await self._scalar(
            select(func.count()).select_from(Article).where(Article.deleted_at.is_(None))
        )
        published = await self._scalar(
            select(func.count())
            .select_from(Article)
            .where(
                Article.deleted_at.is_(None),
                Article.status == ArticleStatus.PUBLISHED,
            )
        )
        return total, published

    async def favorite_total(self) -> int:
        return await self._scalar(select(func.count()).select_from(FundFavorite))

    async def type_distribution(self) -> list[tuple[str, int]]:
        rows = (
            await self.session.execute(
                select(Fund.type, func.count(Fund.id))
                .where(Fund.deleted_at.is_(None))
                .group_by(Fund.type)
                .order_by(func.count(Fund.id).desc())
            )
        ).all()
        return [(row[0], int(row[1])) for row in rows]

    async def avg_return_by_type(self) -> dict[str, float | None]:
        rows = (
            await self.session.execute(
                select(Fund.type, func.avg(FundMetric.return_rate))
                .join(FundMetric, FundMetric.fund_id == Fund.id)
                .where(
                    Fund.deleted_at.is_(None),
                    FundMetric.period == "1y",
                    FundMetric.return_rate.is_not(None),
                )
                .group_by(Fund.type)
            )
        ).all()
        return {row[0]: (float(row[1]) if row[1] is not None else None) for row in rows}

    async def recent_users(self, limit: int = 5) -> list[User]:
        rows = (
            await self.session.execute(select(User).order_by(User.created_at.desc()).limit(limit))
        ).scalars()
        return list(rows)

    async def recent_audits(self, limit: int = 8) -> list[AuditLog]:
        rows = (
            await self.session.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            )
        ).scalars()
        return list(rows)

    async def table_stats(self) -> list[tuple[str, int, str | None]]:
        """库表规模（InnoDB 的行数是估算值，用于展示量级）。"""
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
                    ORDER BY TABLE_ROWS DESC
                    """
                )
            )
        ).all()
        return [(row[0], int(row[1] or 0), row[2] or None) for row in rows]
