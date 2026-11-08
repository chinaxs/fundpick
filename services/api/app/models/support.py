"""会员支持相关模型：反馈工单与密码重置申请。

两者都刻意保留 `user_id` 外键但不级联删除：会员被软删除后，
工单与重置记录仍需作为处理留痕存在。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FeedbackStatus(StrEnum):
    OPEN = "open"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    CLOSED = "closed"


class FeedbackCategory(StrEnum):
    ACCOUNT = "account"
    DATA = "data"
    FUNCTION = "function"
    BUG = "bug"
    OTHER = "other"


class Feedback(TimestampMixin, Base):
    """门户反馈工单。"""

    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_status_created", "status", "created_at"),
        {"comment": "会员反馈工单"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="提交会员"
    )
    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FeedbackCategory.OTHER.value,
        server_default=FeedbackCategory.OTHER.value,
        comment="account / data / function / bug / other",
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="描述")
    contact: Mapped[str | None] = mapped_column(
        String(120), nullable=True, comment="联系方式（留空则用账号邮箱）"
    )
    page_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="出问题的页面地址"
    )
    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(
            FeedbackStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=FeedbackStatus.OPEN,
        server_default=FeedbackStatus.OPEN.value,
        index=True,
        comment="处理状态",
    )
    reply: Mapped[str | None] = mapped_column(Text, nullable=True, comment="公开回复内容")
    handled_by: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="处理人（后台账号快照）"
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="处理时间")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Feedback {self.id} {self.status} {self.title!r}>"


class PasswordResetRequest(Base):
    """密码重置申请。

    没有邮件服务时不假装发送成功：会员提交后生成一条待处理记录，
    客服核实身份后在后台生成一次性链接并线下发给本人；链接 30 分钟过期、
    只能使用一次，使用后撤销该账号全部会话。
    """

    __tablename__ = "password_reset_requests"
    __table_args__ = (
        Index("ix_password_reset_user_created", "user_id", "created_at"),
        {"comment": "会员密码重置申请"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="申请会员"
    )
    token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, comment="令牌摘要（不存明文）"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="令牌过期时间"
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="使用时间")
    requested_ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="申请来源 IP"
    )
    issued_by: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="生成链接的客服账号"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="申请时间"
    )

    @property
    def pending(self) -> bool:
        return self.used_at is None and self.token_hash is None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PasswordResetRequest {self.id} user={self.user_id}>"
