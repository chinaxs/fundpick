"""Prioritized per-fund data issues for admin review and targeted collection."""

from datetime import date, timedelta

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.models.fund_metric import FundMetric
from app.schemas.data_quality import DataQualityIssue, DataQualityReport, DataQualitySummary

NAV_STALE_AFTER_DAYS = 3


class DataQualityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def report(
        self, page: int = 1, page_size: int = 100, keyword: str | None = None
    ) -> DataQualityReport:
        today = date.today()
        stale_before = today - timedelta(days=NAV_STALE_AFTER_DAYS)
        join_condition = and_(FundMetric.fund_id == Fund.id, FundMetric.period == "1y")
        base = (
            select(Fund.id).outerjoin(FundMetric, join_condition).where(Fund.deleted_at.is_(None))
        )
        missing_nav = or_(Fund.latest_nav.is_(None), Fund.latest_nav_date.is_(None))
        lagging_nav = and_(Fund.latest_nav_date.is_not(None), Fund.latest_nav_date < stale_before)
        missing_return = or_(FundMetric.id.is_(None), FundMetric.return_rate.is_(None))
        stale_risk = and_(
            Fund.latest_nav_date.is_not(None),
            or_(
                FundMetric.id.is_(None),
                FundMetric.risk_nav_date.is_distinct_from(Fund.latest_nav_date),
            ),
        )
        missing_profile = or_(Fund.scale.is_(None), Fund.inception_date.is_(None))
        affected = or_(missing_nav, lagging_nav, missing_return, stale_risk, missing_profile)

        total_funds = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(Fund).where(Fund.deleted_at.is_(None))
                )
            ).scalar_one()
        )

        async def count(condition) -> int:
            query = base.where(condition)
            return int(
                (
                    await self.session.execute(select(func.count()).select_from(query.subquery()))
                ).scalar_one()
            )

        summary = DataQualitySummary(
            total_funds=total_funds,
            affected_funds=await count(affected),
            missing_nav=await count(missing_nav),
            lagging_nav=await count(lagging_nav),
            missing_return=await count(missing_return),
            stale_risk=await count(stale_risk),
            missing_profile=await count(missing_profile),
        )

        issue_query = (
            select(Fund.id)
            .outerjoin(FundMetric, join_condition)
            .where(Fund.deleted_at.is_(None), affected)
        )
        if keyword:
            like = f"%{keyword.strip()}%"
            issue_query = issue_query.where(or_(Fund.code.like(like), Fund.name.like(like)))
        total = int(
            (
                await self.session.execute(select(func.count()).select_from(issue_query.subquery()))
            ).scalar_one()
        )
        stmt = (
            select(Fund, FundMetric)
            .outerjoin(FundMetric, join_condition)
            .where(Fund.deleted_at.is_(None), affected)
            .order_by(
                case((Fund.latest_nav_date.is_(None), 0), else_=1),
                Fund.latest_nav_date.asc(),
                Fund.code,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        if keyword:
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(Fund.code.like(like), Fund.name.like(like)))
        rows = (await self.session.execute(stmt)).all()
        items = []
        for fund, metric in rows:
            age = (today - fund.latest_nav_date).days if fund.latest_nav_date else None
            fields = []
            needs_snapshot = False
            needs_risk = False
            if fund.latest_nav is None or fund.latest_nav_date is None:
                fields.append("缺少最新净值")
                needs_snapshot = True
            elif age is not None and age > NAV_STALE_AFTER_DAYS:
                fields.append(f"净值日期滞后 {age} 天")
                needs_snapshot = True
            if metric is None or metric.return_rate is None:
                fields.append("缺少 1 年收益指标")
                needs_snapshot = True
            if fund.latest_nav_date and (
                metric is None or metric.risk_nav_date != fund.latest_nav_date
            ):
                fields.append("风险指标未采集或基准日已过期")
                needs_risk = True
            if fund.scale is None:
                fields.append("缺少基金规模")
            if fund.inception_date is None:
                fields.append("缺少成立日期")
            suggested_mode = "snapshot" if needs_snapshot else "risk" if needs_risk else "detail"
            items.append(
                DataQualityIssue(
                    code=fund.code,
                    name=fund.name,
                    fields=fields,
                    latest_nav_date=fund.latest_nav_date,
                    nav_age_days=age,
                    risk_nav_date=metric.risk_nav_date if metric else None,
                    suggested_mode=suggested_mode,
                )
            )
        return DataQualityReport(
            checked_on=today,
            nav_stale_after_days=NAV_STALE_AFTER_DAYS,
            summary=summary,
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
