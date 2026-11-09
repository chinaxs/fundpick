"""Run pending automatic records without requiring an open browser.

A conditional SQL update claims each retry across workers. Claims expire so a
worker crash cannot strand an application. TransactionService still validates
ownership, cancellation, confirmed history and idempotency at posting time.
"""

import asyncio
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.trade_application import TradeApplication
from app.models.user import User
from app.services.automatic_trade import AutomaticTradeService
from app.trading_calendar import SHANGHAI

logger = get_logger(__name__)
RETRY_MINUTES = 5


def now_local() -> datetime:
    return datetime.now(SHANGHAI).replace(tzinfo=None)


async def reconcile_due(limit: int = 50) -> dict[str, int]:
    now = now_local()
    due = (
        TradeApplication.status == "pending",
        TradeApplication.automatic_processing.is_(True),
        TradeApplication.deleted_at.is_(None),
        TradeApplication.user_id.in_(
            select(User.id).where(User.is_active.is_(True), User.deleted_at.is_(None))
        ),
        or_(TradeApplication.next_retry_at.is_(None), TradeApplication.next_retry_at <= now),
    )
    async with async_session_factory() as session:
        candidates = (
            await session.execute(
                select(TradeApplication.id, TradeApplication.user_id)
                .where(*due)
                .order_by(
                    TradeApplication.next_retry_at,
                    TradeApplication.expected_nav_on,
                    TradeApplication.submitted_at,
                    TradeApplication.id,
                )
                .limit(limit)
            )
        ).all()
    result = {"checked": 0, "recorded": 0, "pending": 0, "failed": 0}
    for application_id, user_id in candidates:
        async with async_session_factory() as session:
            claimed = await session.execute(
                update(TradeApplication)
                .where(TradeApplication.id == application_id, *due)
                .values(last_attempt_at=now, next_retry_at=now + timedelta(minutes=RETRY_MINUTES))
            )
            await session.commit()
            if not cast(CursorResult, claimed).rowcount:
                continue
            result["checked"] += 1
            try:
                outcome = await AutomaticTradeService(session).resolve(user_id, application_id)
                result[outcome.status] += 1
            except Exception as error:
                await session.rollback()
                result["failed"] += 1
                # User cancellation or another worker posting is a normal race.
                await session.execute(
                    update(TradeApplication)
                    .where(
                        TradeApplication.id == application_id,
                        TradeApplication.status == "pending",
                        TradeApplication.deleted_at.is_(None),
                    )
                    .values(
                        processing_message="自动核对暂未完成，将在5分钟后重试；未知净值或费用不会提前入账"
                    )
                )
                await session.commit()
                logger.warning("自动入账重试 id=%s error=%s", application_id, type(error).__name__)
    return result


async def run_reconciliation_worker(interval_seconds: int = 60) -> None:
    logger.info("自动入账后台检查已启动，间隔%s秒", interval_seconds)
    while True:
        try:
            result = await reconcile_due()
            if result["checked"]:
                logger.info("自动入账检查: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("自动入账后台检查失败")
        await asyncio.sleep(max(10, interval_seconds))
