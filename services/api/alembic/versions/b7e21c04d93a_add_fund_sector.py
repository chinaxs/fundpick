"""add fund sector column

Revision ID: b7e21c04d93a
Revises: c3f8a1d92b47
Create Date: 2026-11-06

主题板块：按基金名称/跟踪指数推导的板块标签，NULL 表示无明显主题。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e21c04d93a"
down_revision: Union[str, None] = "c3f8a1d92b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funds",
        sa.Column("sector", sa.String(length=32), nullable=True, comment="主题板块"),
    )
    op.create_index("ix_funds_sector", "funds", ["sector"])


def downgrade() -> None:
    op.drop_index("ix_funds_sector", table_name="funds")
    op.drop_column("funds", "sector")
