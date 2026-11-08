"""add transfer group to portfolio flows

Revision ID: e5c9a2b71d68
Revises: d4a8b1f30c95
Create Date: 2026-11-08

转换是"同一笔钱从 A 换到 B"，拆成两条独立流水后需要可追溯的关联，
否则成本结转与删除都只能靠日期猜。`transfer_group` 把配对的
转出/转入绑在一起。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5c9a2b71d68"
down_revision: Union[str, None] = "d4a8b1f30c95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fund_portfolio_flows",
        sa.Column("transfer_group", sa.String(length=36), nullable=True, comment="转换配对标识"),
    )
    op.create_index(
        "ix_fund_portfolio_flows_transfer_group",
        "fund_portfolio_flows",
        ["transfer_group"],
    )


def downgrade() -> None:
    op.drop_index("ix_fund_portfolio_flows_transfer_group", table_name="fund_portfolio_flows")
    op.drop_column("fund_portfolio_flows", "transfer_group")
