"""可撤销登录会话与持久化登录失败窗口。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_owner", "scope", "subject_id"),
        Index("ix_auth_sessions_expiry", "expires_at"),
        {"comment": "门户与后台登录会话"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="会话 ID")
    scope: Mapped[str] = mapped_column(String(16), nullable=False, comment="portal/staff")
    subject_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="所属账号 ID")
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="当前刷新令牌 SHA-256 摘要"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="会话过期时间")
    last_rotated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="最近刷新时间"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="撤销时间")


class AuthLoginAttempt(Base):
    __tablename__ = "auth_login_attempts"
    __table_args__ = {"comment": "按账号与来源限制登录失败次数"}

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True, comment="账号/IP HMAC")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="窗口内失败次数")
    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
