"""add position nav source columns

Revision ID: f2b71d4e9c30
Revises: e5a93c70d1b4
Create Date: 2026-11-06

净值不再由用户手工录入：记录系统折算时采用的历史净值日期与来源，
便于在明细里如实展示"按哪天的净值折算"，也避免每次列表重复查净值表。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b71d4e9c30"
down_revision: Union[str, None] = "e5a93c70d1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fund_positions",
        sa.Column("cost_nav_date", sa.Date(), nullable=True, comment="成本净值对应的交易日"),
    )
    op.add_column(
        "fund_positions",
        sa.Column(
            "nav_source",
            sa.String(16),
            nullable=False,
            server_default="history",
            comment="净值来源：history=历史净值 / latest=回退最新净值",
        ),
    )


def downgrade() -> None:
    op.drop_column("fund_positions", "nav_source")
    op.drop_column("fund_positions", "cost_nav_date")
