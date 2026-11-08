"""会员访问活跃日表。

为什么不用 `auth_sessions.created_at`：会话只在登录/注册时创建，
忠实用户连续 30 天每天来，也不会新增会话，活跃与回访会被严重低估。

这里按"天"记录一次访问（唯一键 user_id + activity_date），
由鉴权依赖在通过校验后写入，并做进程内节流，避免每个请求都写库。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemberActivity(Base):
    __tablename__ = "member_activity"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_member_activity_day"),
        Index("ix_member_activity_date", "activity_date"),
        {"comment": "会员每日访问记录"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="会员",
    )
    activity_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="访问日期（北京时间）"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="当日最近一次访问时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MemberActivity user={self.user_id} {self.activity_date}>"
