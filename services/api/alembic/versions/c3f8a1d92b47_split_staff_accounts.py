"""split staff accounts into staff_users

把后台账号从 users 表拆到独立的 staff_users 表：
1. 建表（结构与原 users 的员工相关字段一致，去掉 is_staff）；
2. 迁移现有后台账号（is_staff=1 或 is_superuser=1 的行）；
3. users 表去掉 is_staff / is_superuser 两列，成为纯门户会员表。

Revision ID: c3f8a1d92b47
Revises: 7de327eabdf0
Create Date: 2026-11-06 07:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1d92b47"
down_revision: str | None = "7de327eabdf0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "id",
    "username",
    "email",
    "hashed_password",
    "full_name",
    "avatar_url",
    "is_active",
    "is_superuser",
    "last_login_at",
    "created_at",
    "updated_at",
    "deleted_at",
)


def upgrade() -> None:
    op.create_table(
        "staff_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("username", sa.String(length=50), nullable=False, comment="登录名"),
        sa.Column("email", sa.String(length=120), nullable=True, comment="邮箱"),
        sa.Column("hashed_password", sa.String(length=255), nullable=False, comment="密码哈希（bcrypt）"),
        sa.Column("full_name", sa.String(length=50), nullable=True, comment="姓名"),
        sa.Column("avatar_url", sa.String(length=255), nullable=True, comment="头像地址"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default="0", comment="是否超级管理员（可管理员工账号与系统信息）"
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True, comment="最后登录时间"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="更新时间"
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="软删除时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="后台员工账号表（与门户会员分离）",
    )
    op.create_index(op.f("ix_staff_users_username"), "staff_users", ["username"], unique=True)
    op.create_index(op.f("ix_staff_users_email"), "staff_users", ["email"], unique=True)

    cols = ", ".join(_COLUMNS)
    op.execute(
        f"""
        INSERT INTO staff_users ({cols})
        SELECT {cols}
        FROM users
        WHERE is_staff = 1 OR is_superuser = 1
        """
    )
    # 是"迁移"不是"复制"：员工账号搬走后，从会员表删除原行，
    # 两边从此互不可见（员工登不了门户，会员也进不了后台）。
    op.execute("DELETE FROM users WHERE is_staff = 1 OR is_superuser = 1")

    op.drop_column("users", "is_staff")
    op.drop_column("users", "is_superuser")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default="0", comment="是否后台账号"),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default="0", comment="是否超级管理员"
        ),
    )
    op.execute("UPDATE users SET is_staff = 1 WHERE id IN (SELECT id FROM staff_users)")
    op.execute("UPDATE users u SET is_superuser = 1 WHERE u.username = 'admin'")
    op.drop_index(op.f("ix_staff_users_email"), table_name="staff_users")
    op.drop_index(op.f("ix_staff_users_username"), table_name="staff_users")
    op.drop_table("staff_users")
