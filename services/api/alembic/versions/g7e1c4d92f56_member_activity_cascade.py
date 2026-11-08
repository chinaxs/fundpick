"""member activity cascade on user delete

Revision ID: g7e1c4d92f56
Revises: f6d3b8c2194e
Create Date: 2026-11-08

会员被删除时访问记录一并删除：活跃统计是附属数据，
不该因为一张统计表挡住账号删除。
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "g7e1c4d92f56"
down_revision: Union[str, None] = "f6d3b8c2194e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("member_activity_ibfk_1", "member_activity", type_="foreignkey")
    op.create_foreign_key(
        "fk_member_activity_user",
        "member_activity",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_member_activity_user", "member_activity", type_="foreignkey")
    op.create_foreign_key(
        "member_activity_ibfk_1",
        "member_activity",
        "users",
        ["user_id"],
        ["id"],
    )
