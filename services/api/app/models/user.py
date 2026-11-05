"""用户模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class User(TimestampMixin, SoftDeleteMixin, Base):
    """后台账号 / 门户会员统一用户表。"""

    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    username: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True, comment="登录名"
    )
    email: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True, index=True, comment="邮箱"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希（bcrypt）"
    )
    full_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="姓名 / 昵称")
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像地址")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", comment="是否启用"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", comment="是否超级管理员"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后登录时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r}>"
