"""自动记账所需数据：按净值日补查，交易费率独立缓存且保留来源。"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic

from sqlalchemy.dialects.mysql import insert

from app.core.logging import get_logger
from app.datasources import get_provider
from app.datasources.fund_fees import SOURCE
from app.db.session import async_session_factory
from app.models.fund_fee_schedule import FundFeeSchedule
from app.models.fund_nav import FundNav
from app.trading_calendar import SHANGHAI

logger = get_logger(__name__)
_attempts: dict[str, float] = {}


async def lookup_rules(fund_id: int, code: str):
    """正缓存24小时，空结果5分钟，避免失败时每行/每秒请求上游。"""
    async with async_session_factory() as session:
        cached = await session.get(FundFeeSchedule, fund_id)
        ttl = timedelta(hours=24) if cached and cached.rules else timedelta(minutes=5)
        if cached is not None:
            complete = not cached.rules or any(
                row["kind"] == "confirmation" for row in cached.rules
            )
            if complete and datetime.now() - cached.fetched_at < ttl:
                return cached.rules, cached.source_url, cached.fetched_at
    key = f"fees:{code}"
    if monotonic() - _attempts.get(key, -1e9) < 30:
        return [], SOURCE.format(code=code), None
    _attempts[key] = monotonic()
    try:
        rules = await asyncio.wait_for(asyncio.to_thread(get_provider().transaction_fees, code), 10)
    except Exception as exc:
        logger.info("交易费率 %s 暂不可用: %s", code, type(exc).__name__)
        rules = []
    fetched_at = datetime.now()
    async with async_session_factory() as session:
        statement = insert(FundFeeSchedule).values(
            fund_id=fund_id, rules=rules, source_url=SOURCE.format(code=code), fetched_at=fetched_at
        )
        await session.execute(statement.on_duplicate_key_update(rules=rules, fetched_at=fetched_at))
        await session.commit()
    return rules, SOURCE.format(code=code), fetched_at


async def lookup_nav(repo, fund, day):
    """先查本地精确日期，不存在才补查同日；绝不使用最近净值代替。"""
    value = await repo.exact_nav(fund, day)
    if value is not None or day > datetime.now(SHANGHAI).date():
        return value
    key = f"nav:{fund.code}:{day}"
    if monotonic() - _attempts.get(key, -1e9) < 300:
        return None
    _attempts[key] = monotonic()
    try:
        points = await asyncio.wait_for(
            asyncio.to_thread(get_provider().nav_history, fund.code), 10
        )
    except Exception as exc:
        logger.info("交易净值 %s 暂不可用: %s", fund.code, type(exc).__name__)
        return None
    point = next((item for item in points if item.nav_date == day), None)
    if point is None or point.unit_nav <= 0:
        return None
    value = Decimal(str(point.unit_nav))
    async with async_session_factory() as session:
        statement = insert(FundNav).values(
            fund_id=fund.id, nav_date=day, unit_nav=value, daily_return=point.daily_return
        )
        await session.execute(statement.on_duplicate_key_update(unit_nav=value))
        await session.commit()
    return value
