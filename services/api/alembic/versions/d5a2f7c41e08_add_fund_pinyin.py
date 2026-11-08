"""add fund pinyin columns

Revision ID: d5a2f7c41e08
Revises: a1c7e95b3d20
Create Date: 2026-11-07

搜索用的派生列：名称全拼与拼音首字母。
库里 28k 只基金，`LIKE '%xx%'` 用不到索引，所以只加列不加索引；
由 `scripts/sync_funds.py --mode pinyin` 回填，日常同步时顺带维护。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5a2f7c41e08"
down_revision: Union[str, None] = "a1c7e95b3d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funds",
        sa.Column(
            "name_pinyin",
            sa.String(length=120),
            nullable=True,
            comment="名称全拼（小写无分隔），供模糊搜索",
        ),
    )
    op.add_column(
        "funds",
        sa.Column(
            "name_initials",
            sa.String(length=60),
            nullable=True,
            comment="名称拼音首字母，供模糊搜索",
        ),
    )


def downgrade() -> None:
    op.drop_column("funds", "name_initials")
    op.drop_column("funds", "name_pinyin")
