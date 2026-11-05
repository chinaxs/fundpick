"""安全相关：密码哈希与 JWT 签发 / 校验。"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings

TokenType = Literal["access", "refresh"]


# ---------------------------------------------------------------- 密码
def hash_password(plain_password: str) -> str:
    """生成 bcrypt 哈希。bcrypt 仅取前 72 字节，超长直接拒绝。"""
    raw = plain_password.encode("utf-8")
    if len(raw) > 72:
        raise ValueError("密码过长（UTF-8 编码后不得超过 72 字节）")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- JWT
def create_token(
    subject: str | int,
    token_type: TokenType = "access",
    expires_delta: timedelta | None = None,
    **extra_claims: Any,
) -> str:
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            if token_type == "access"
            else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        **extra_claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """解码 token，失败抛 ValueError（由上层转成 401）。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError as exc:
        raise ValueError("登录已过期，请重新登录") from exc
    except InvalidTokenError as exc:
        raise ValueError("无效的令牌") from exc

    if expected_type and payload.get("type") != expected_type:
        raise ValueError("令牌类型不匹配")
    return payload
