"""后台运营统计服务。"""

from __future__ import annotations

import platform
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.runtime import STARTED_AT
from app.repositories.admin_stats import AdminStatsRepository
from app.schemas.admin import (
    AuditLogRead,
    CoverageItem,
    DashboardOverview,
    RecentUser,
    SystemInfo,
    TableStat,
    TypeCount,
)
from app.services.fund import TYPE_LABELS

# 覆盖率展示顺序与文案
COVERAGE_LABELS: list[tuple[str, str]] = [
    ("latest_nav", "最新净值"),
    ("nav", "净值序列"),
    ("metric", "区间指标"),
    ("scale", "规模"),
    ("inception_date", "成立日期"),
    ("manager", "基金经理"),
    ("company", "基金公司"),
]


class AdminStatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.stats = AdminStatsRepository(session)

    async def dashboard(self) -> DashboardOverview:
        coverage_raw = await self.stats.fund_field_coverage()
        total = coverage_raw["total"]

        coverage = [
            CoverageItem(
                key=key,
                label=label,
                covered=coverage_raw.get(key, 0),
                total=total,
                percent=round(coverage_raw.get(key, 0) / total * 100, 1) if total else 0.0,
            )
            for key, label in COVERAGE_LABELS
        ]

        _, latest_nav_date = await self.stats.nav_stats()
        lag = (date.today() - latest_nav_date).days if latest_nav_date else None

        user_total, user_staff, user_new_7d = await self.stats.user_counts()
        article_total, article_published = await self.stats.article_counts()

        type_rows = await self.stats.type_distribution()
        avg_returns = await self.stats.avg_return_by_type()

        return DashboardOverview(
            funds_total=total,
            companies_total=await self.stats.company_total(),
            managers_total=await self.stats.manager_total(),
            nav_latest_date=latest_nav_date,
            nav_date_lag_days=lag,
            coverage=coverage,
            user_total=user_total,
            user_staff=user_staff,
            user_new_7d=user_new_7d,
            article_total=article_total,
            article_published=article_published,
            favorite_total=await self.stats.favorite_total(),
            type_distribution=[
                TypeCount(
                    type=fund_type,
                    label=TYPE_LABELS.get(fund_type, fund_type),
                    count=count,
                    avg_return=round(avg, 2) if (avg := avg_returns.get(fund_type)) else None,
                )
                for fund_type, count in type_rows
            ],
            recent_users=[
                RecentUser(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    created_at=user.created_at,
                )
                for user in await self.stats.recent_users()
            ],
            recent_audits=[
                AuditLogRead.model_validate(log, from_attributes=True)
                for log in await self.stats.recent_audits()
            ],
            server_time=datetime.now(),
        )

    async def system_info(self) -> SystemInfo:
        tables = [
            TableStat(name=name, rows=rows, comment=comment)
            for name, rows, comment in await self.stats.table_stats()
        ]
        uptime = int((datetime.now() - STARTED_AT).total_seconds())

        return SystemInfo(
            app_name=settings.APP_NAME,
            version=settings.VERSION,
            environment=settings.APP_ENV,
            debug=settings.DEBUG,
            python_version=platform.python_version(),
            # 不输出账号密码
            database=f"mysql://{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}",
            started_at=STARTED_AT,
            uptime_seconds=uptime,
            tables=tables,
        )
