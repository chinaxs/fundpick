"""add net amount to portfolio flows

Revision ID: j1d5f3a9c84b
Revises: i9c4e1f82a37
Create Date: 2026-11-09

转换时源侧转出 100 元、目标侧只到账 90 元，差的 10 元是费用/损耗。
只存一个金额时，这 10 元会从收益里凭空消失。

`cash_amount` 保留毛金额（源侧转出），`net_amount` 存实际结转净额（目标侧到账），
账本用净额与结转成本比较，差额自然进入已实现收益。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j1d5f3a9c84b"
down_revision: Union[str, None] = "i9c4e1f82a37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fund_portfolio_flows",
        sa.Column(
            "net_amount",
            sa.Numeric(18, 2),
            nullable=True,
            comment="转换转出实际结转净额",
        ),
    )


def downgrade() -> None:
    op.drop_column("fund_portfolio_flows", "net_amount")
