"""add member activity

Revision ID: f6d3b8c2194e
Revises: e5c9a2b71d68
Create Date: 2026-11-08

会员每日访问记录：每日活跃与回访不能再拿"登录会话创建时间"代替，
否则持续登录的用户永远只算一次。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6d3b8c2194e"
down_revision: Union[str, None] = "e5c9a2b71d68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "member_activity",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="会员"),
        sa.Column("activity_date", sa.Date(), nullable=False, comment="访问日期"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, comment="最近访问时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "activity_date", name="uq_member_activity_day"),
        comment="会员每日访问记录",
    )
    op.create_index("ix_member_activity_user_id", "member_activity", ["user_id"])
    op.create_index("ix_member_activity_date", "member_activity", ["activity_date"])


def downgrade() -> None:
    op.drop_index("ix_member_activity_date", table_name="member_activity")
    op.drop_index("ix_member_activity_user_id", table_name="member_activity")
    op.drop_table("member_activity")
