"""Refresh accessed funds with bounded upstream requests and persistent backoff."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from weakref import WeakValueDictionary

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.datasources import get_provider
from app.models.fund import Fund
from app.models.fund_data_check import FundDataCheck
from app.models.fund_holding import FundHolding
from app.models.fund_nav import FundNav
from app.trading_calendar import SHANGHAI

logger = get_logger(__name__)
_locks: WeakValueDictionary[tuple[int, str], asyncio.Lock] = WeakValueDictionary()


async def refresh_data(session: AsyncSession, fund: Fund, kind: str) -> None:
    key = (fund.id, kind)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        # Lock one persisted key across workers; the first caller inserts the key.
        claim = insert(FundDataCheck).values(
            fund_id=key[0],
            kind=kind,
            checked_at=datetime(1970, 1, 1),
            succeeded=False,
        )
        await session.execute(claim.on_duplicate_key_update(fund_id=key[0]))
        check = await session.scalar(
            select(FundDataCheck)
            .where(FundDataCheck.fund_id == fund.id, FundDataCheck.kind == kind)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        now = datetime.now(SHANGHAI).replace(tzinfo=None)
        ttl = timedelta(minutes=30 if kind == "navs" else 360)
        if check and not check.succeeded:
            ttl = timedelta(minutes=5)
        if check and now - check.checked_at < ttl:
            await session.commit()
            return

        code = fund.code
        provider = get_provider()
        rows: list[dict[str, Any]]
        try:
            if kind == "navs":
                source = await asyncio.wait_for(
                    asyncio.to_thread(provider.nav_history, fund.code), 8
                )
                points = {
                    p.nav_date: p for p in source if p.unit_nav > 0 and p.nav_date <= now.date()
                }
                rows = [
                    {
                        "fund_id": fund.id,
                        "nav_date": p.nav_date,
                        "unit_nav": p.unit_nav,
                        "daily_return": p.daily_return,
                    }
                    for p in points.values()
                ]
                await _upsert(session, FundNav, rows, ["unit_nav", "daily_return"])
                if points:
                    newest = points[max(points)]
                    if fund.latest_nav_date is None or newest.nav_date >= fund.latest_nav_date:
                        fund.latest_nav_date = newest.nav_date
                        fund.latest_nav = Decimal(str(newest.unit_nav))
            else:
                holdings = await asyncio.wait_for(
                    asyncio.to_thread(provider.fund_holdings, fund.code, str(now.year)), 8
                )
                if not holdings:
                    holdings = await asyncio.wait_for(
                        asyncio.to_thread(provider.fund_holdings, fund.code, str(now.year - 1)), 8
                    )
                rows = [
                    {
                        "fund_id": fund.id,
                        "quarter": h.quarter,
                        "stock_code": h.stock_code,
                        "stock_name": h.stock_name,
                        "rank": h.rank or None,
                        "ratio": h.ratio,
                        "shares": h.shares,
                        "market_value": h.market_value,
                    }
                    for h in holdings
                ]
                await _upsert(
                    session,
                    FundHolding,
                    rows,
                    ["stock_name", "rank", "ratio", "shares", "market_value"],
                )
            succeeded = bool(rows)
            message = None if succeeded else "上游暂未返回可用数据"
        except Exception as error:
            await session.rollback()
            succeeded, message = False, "上游暂不可用，保留已有数据"
            logger.info("基金%s %s更新暂不可用: %s", code, kind, type(error).__name__)
        # Never remove valid stored rows or mark old data as new after a failure.
        statement = insert(FundDataCheck).values(
            fund_id=key[0], kind=kind, checked_at=now, succeeded=succeeded, message=message
        )
        await session.execute(
            statement.on_duplicate_key_update(checked_at=now, succeeded=succeeded, message=message)
        )
        await session.commit()
        await session.refresh(fund)


async def _upsert(session: AsyncSession, model: Any, rows: list[dict], fields: list[str]) -> None:
    for offset in range(0, len(rows), 500):
        statement = insert(model).values(rows[offset : offset + 500])
        await session.execute(
            statement.on_duplicate_key_update(
                **{key: getattr(statement.inserted, key) for key in fields}
            )
        )
