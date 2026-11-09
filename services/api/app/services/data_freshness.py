"""Beijing disclosure deadlines and trading-day based fund freshness.

22:00 is an operational check time for ordinary domestic NAVs, not a promise
that every fund company publishes by then. QDII/FOF/suspended products need
separate review and must not be treated as a failed domestic daily feed.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Fund, FundNav, SyncJob, SyncSchedule, TradeApplication
from app.trading_calendar import SHANGHAI, latest_trading_day, trading_day_or_none

DISCLOSURE_CHECK_HOUR = 22
SPECIAL_TYPES = ("qdii", "fof", "money", "other")


def check_time(now: datetime | None = None) -> datetime:
    now = now or datetime.now(SHANGHAI)
    return now.replace(tzinfo=SHANGHAI) if now.tzinfo is None else now.astimezone(SHANGHAI)


def expected_nav_date(now: datetime | None = None) -> date | None:
    now = check_time(now)
    cutoff = now.date() if now.hour >= DISCLOSURE_CHECK_HOUR else now.date() - timedelta(days=1)
    return latest_trading_day(cutoff)


def freshness(latest: date | None, now: datetime | None = None) -> dict:
    now = check_time(now)
    expected = expected_nav_date(now)
    lag = None
    if expected and latest:
        days = (expected - latest).days
        if 0 <= days <= 370:
            values = [
                trading_day_or_none(latest + timedelta(days=offset))
                for offset in range(1, days + 1)
            ]
            lag = None if any(v is None for v in values) else sum(v is True for v in values)
        elif days < 0:
            lag = 0
    if expected is None:
        state, message = "unknown", "交易日历未覆盖，无法自动判断是否滞后"
    elif latest is None:
        state, message = "missing", "暂无已披露净值"
    elif latest < expected:
        state, message = "lagging", f"未达到应披露基准 {expected}，需检查同步与上游披露"
    elif trading_day_or_none(now.date()) and now.hour < DISCLOSURE_CHECK_HOUR:
        state, message = "current", f"已覆盖 {expected}；今日净值收盘后陆续公布，22:00起核对"
    else:
        state, message = "current", f"已覆盖应披露基准 {expected}"
    return {
        "expected_nav_date": expected,
        "calendar_known": expected is not None,
        "nav_lag_trading_days": lag,
        "freshness_state": state,
        "freshness_message": message,
        "disclosure_check_hour": DISCLOSURE_CHECK_HOUR,
    }


async def sync_status(session: AsyncSession, now: datetime | None = None) -> dict:
    now = check_time(now)
    expected = expected_nav_date(now)
    active = Fund.deleted_at.is_(None)
    routine = (active, Fund.status == "open", Fund.type.not_in(SPECIAL_TYPES))
    latest = await session.scalar(select(func.max(Fund.latest_nav_date)).where(active))
    nav_rows = await session.scalar(select(func.count()).select_from(FundNav))
    total = await session.scalar(select(func.count()).select_from(Fund).where(active))
    latest_routine = await session.scalar(select(func.max(Fund.latest_nav_date)).where(*routine))
    missing = or_(Fund.latest_nav.is_(None), Fund.latest_nav_date.is_(None))
    current = (
        await session.scalar(
            select(func.count())
            .select_from(Fund)
            .where(*routine, Fund.latest_nav.is_not(None), Fund.latest_nav_date >= expected)
        )
        if expected
        else None
    )
    lagging = (
        await session.scalar(
            select(func.count()).select_from(Fund).where(*routine, Fund.latest_nav_date < expected)
        )
        if expected
        else None
    )
    missing_count = await session.scalar(
        select(func.count()).select_from(Fund).where(*routine, missing)
    )
    pending = (
        TradeApplication.status == "pending",
        TradeApplication.automatic_processing.is_(True),
        TradeApplication.deleted_at.is_(None),
    )
    last_auto = await session.scalar(select(func.max(TradeApplication.last_attempt_at)))
    last_sync = await session.scalar(
        select(SyncJob.finished_at)
        .where(
            SyncJob.mode.in_(["quick", "snapshot", "tracked", "navs"]),
            SyncJob.status.in_(["success", "partial_success"]),
        )
        .order_by(SyncJob.finished_at.desc())
        .limit(1)
    )
    return {
        "fund_total": total or 0,
        "nav_rows": nav_rows or 0,
        "latest_nav_date": latest,
        **freshness(latest_routine, now),
        "checked_at": now,
        "current_funds": current,
        "lagging_funds": lagging,
        "missing_nav_funds": missing_count or 0,
        "special_funds": await session.scalar(
            select(func.count())
            .select_from(Fund)
            .where(active, or_(Fund.type.in_(SPECIAL_TYPES), Fund.status != "open"))
        ),
        "scheduler_enabled": settings.SYNC_SCHEDULER_ENABLED,
        "enabled_schedules": await session.scalar(
            select(func.count()).select_from(SyncSchedule).where(SyncSchedule.enabled.is_(True))
        ),
        "last_data_sync_at": last_sync,
        "auto_reconcile_enabled": settings.AUTO_RECONCILE_ENABLED,
        "auto_reconcile_interval_seconds": settings.AUTO_RECONCILE_INTERVAL_SECONDS,
        "pending_automatic": await session.scalar(
            select(func.count()).select_from(TradeApplication).where(*pending)
        ),
        "last_automatic_check_at": last_auto,
    }
