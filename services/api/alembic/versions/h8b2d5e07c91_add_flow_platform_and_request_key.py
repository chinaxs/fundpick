"""add platform and request key to portfolio flows

Revision ID: h8b2d5e07c91
Revises: g7e1c4d92f56
Create Date: 2026-11-08

公司行为必须归属确定平台：旧模型只有基金维度，一笔"全基金再投"会在
A、B 两个平台各加一次，各自算出可卖份额，合计超过全基金持仓。

`request_key` 用于幂等：网络重试不应重复记录同一笔分红/再投/转换。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8b2d5e07c91"
down_revision: Union[str, None] = "g7e1c4d92f56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fund_portfolio_flows",
        sa.Column("platform", sa.String(length=80), nullable=True, comment="归属平台"),
    )
    op.add_column(
        "fund_portfolio_flows",
        sa.Column("request_key", sa.String(length=64), nullable=True, comment="幂等键"),
    )
    op.create_index(
        "ix_fund_portfolio_flows_platform", "fund_portfolio_flows", ["platform"]
    )
    op.create_index(
        "uq_portfolio_flow_request",
        "fund_portfolio_flows",
        ["user_id", "request_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_portfolio_flow_request", table_name="fund_portfolio_flows")
    op.drop_index("ix_fund_portfolio_flows_platform", table_name="fund_portfolio_flows")
    op.drop_column("fund_portfolio_flows", "request_key")
    op.drop_column("fund_portfolio_flows", "platform")
