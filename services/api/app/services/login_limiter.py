"""Database-backed login throttling shared across API workers."""

import hmac
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import case, delete
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.models.auth_session import AuthLoginAttempt

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
LOCK_DURATION = timedelta(minutes=15)
_CLEANUP_EVERY = 100
_failure_count = 0


def login_key(scope: str, identifier: str, client_ip: str | None) -> str:
    value = f"{scope}\0{identifier.strip().casefold()}\0{client_ip or 'unknown'}"
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), sha256).hexdigest()


async def check_login_allowed(session: AsyncSession, key_hash: str) -> None:
    row = await session.get(AuthLoginAttempt, key_hash)
    if row and row.locked_until and row.locked_until > datetime.now():
        raise RateLimitError("登录失败次数过多，请 15 分钟后重试")


async def record_login_failure(session: AsyncSession, key_hash: str) -> None:
    global _failure_count
    now = datetime.now()
    window_start = now - WINDOW
    expired = AuthLoginAttempt.window_started_at <= window_start
    stmt = insert(AuthLoginAttempt).values(
        key_hash=key_hash,
        failure_count=1,
        window_started_at=now,
        locked_until=None,
    )
    stmt = stmt.on_duplicate_key_update(
        [
            (
                "locked_until",
                case(
                    (expired, None),
                    (AuthLoginAttempt.failure_count >= MAX_FAILURES - 1, now + LOCK_DURATION),
                    else_=AuthLoginAttempt.locked_until,
                ),
            ),
            (
                "failure_count",
                case((expired, 1), else_=AuthLoginAttempt.failure_count + 1),
            ),
            (
                "window_started_at",
                case((expired, now), else_=AuthLoginAttempt.window_started_at),
            ),
        ]
    )
    await session.execute(stmt)
    _failure_count += 1
    if _failure_count % _CLEANUP_EVERY == 0:
        await session.execute(
            delete(AuthLoginAttempt).where(
                AuthLoginAttempt.window_started_at < now - timedelta(days=1)
            )
        )
    await session.commit()


async def clear_login_failures(session: AsyncSession, key_hash: str) -> None:
    await session.execute(delete(AuthLoginAttempt).where(AuthLoginAttempt.key_hash == key_hash))
    await session.commit()
