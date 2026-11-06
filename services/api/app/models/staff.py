"""后台员工账号模型。

与门户会员（`users` 表）**完全独立**：
- 登录入口不同：`/admin/auth/login` 只查这张表；
- 令牌带 `scope=staff`，即使 ID 与门户会员撞号也互相调不动；
- 门户侧的注册、自选等业务永远碰不到这里。

一张独立的表也让"员工离职禁用账号"与"会员封禁"互不影响。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class StaffUser(TimestampMixin, SoftDeleteMixin, Base):
    """后台员工账号（可登录管理后台）。"""

    __tablename__ = "staff_users"
    __table_args__ = {"comment": "后台员工账号表（与门户会员分离）"}

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
    full_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="姓名")
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像地址")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", comment="是否启用"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="是否超级管理员（可管理员工账号与系统信息）",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后登录时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StaffUser id={self.id} username={self.username!r}>"
