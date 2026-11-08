"""Persistent, revocable login sessions shared by portal and staff auth."""

from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import TokenScope, create_token, decode_token
from app.models.auth_session import AuthSession
from app.schemas.auth import TokenResponse


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def issue_tokens(session: AsyncSession, subject_id: int, scope: TokenScope) -> TokenResponse:
    session_id = str(uuid4())
    refresh_token = create_token(
        subject_id, "refresh", scope=scope, sid=session_id, jti=str(uuid4())
    )
    access_token = create_token(subject_id, "access", scope=scope, sid=session_id)
    now = datetime.now()
    await session.execute(
        delete(AuthSession).where(
            (AuthSession.expires_at < now - timedelta(days=30))
            | (AuthSession.revoked_at < now - timedelta(days=30))
        )
    )
    session.add(
        AuthSession(
            id=session_id,
            scope=scope,
            subject_id=subject_id,
            refresh_token_hash=token_hash(refresh_token),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            last_rotated_at=now,
        )
    )
    await session.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def validate_access_session(
    session: AsyncSession, payload: dict, subject_id: int, scope: TokenScope
) -> bool:
    session_id = payload.get("sid")
    if not isinstance(session_id, str):
        return False
    auth_session = await session.get(AuthSession, session_id)
    return bool(
        auth_session
        and auth_session.scope == scope
        and auth_session.subject_id == subject_id
        and auth_session.revoked_at is None
        and auth_session.expires_at > datetime.now()
    )


async def rotate_refresh_token(
    session: AsyncSession, refresh_token: str, scope: TokenScope
) -> tuple[AuthSession, int]:
    payload = decode_token(refresh_token, expected_type="refresh", expected_scope=scope)
    session_id = payload.get("sid")
    if not isinstance(session_id, str):
        raise UnauthorizedError("刷新令牌已失效")
    auth_session = (
        await session.execute(
            select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        )
    ).scalar_one_or_none()
    now = datetime.now()
    if (
        auth_session is None
        or auth_session.scope != scope
        or auth_session.subject_id != int(payload["sub"])
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or auth_session.refresh_token_hash != token_hash(refresh_token)
    ):
        raise UnauthorizedError("刷新令牌已使用、撤销或过期")
    return auth_session, int(payload["sub"])


async def finish_refresh(
    session: AsyncSession, auth_session: AuthSession, subject_id: int, scope: TokenScope
) -> TokenResponse:
    now = datetime.now()
    refresh_token = create_token(
        subject_id, "refresh", scope=scope, sid=auth_session.id, jti=str(uuid4())
    )
    access_token = create_token(subject_id, "access", scope=scope, sid=auth_session.id)
    auth_session.refresh_token_hash = token_hash(refresh_token)
    auth_session.last_rotated_at = now
    auth_session.expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await session.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def revoke_from_refresh(session: AsyncSession, refresh_token: str, scope: TokenScope) -> None:
    payload = decode_token(refresh_token, expected_type="refresh", expected_scope=scope)
    session_id = payload.get("sid")
    if not isinstance(session_id, str):
        return
    auth_session = (
        await session.execute(
            select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        )
    ).scalar_one_or_none()
    if (
        auth_session is None
        or auth_session.scope != scope
        or auth_session.subject_id != int(payload["sub"])
        or auth_session.revoked_at is not None
    ):
        return
    auth_session.revoked_at = datetime.now()
    await session.commit()


async def revoke_all_for_account(session: AsyncSession, scope: TokenScope, subject_id: int) -> None:
    await revoke_sessions_for_accounts(session, scope, [subject_id])


async def revoke_sessions_for_accounts(
    session: AsyncSession, scope: TokenScope, subject_ids: list[int]
) -> None:
    if not subject_ids:
        return
    await session.execute(
        update(AuthSession)
        .where(
            AuthSession.scope == scope,
            AuthSession.subject_id.in_(subject_ids),
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now())
    )
