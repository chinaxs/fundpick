"""add portfolio flows

Revision ID: d4a8b1f30c95
Revises: c9f3a7d82e14
Create Date: 2026-11-08

持仓补充流水：分红、红利再投、拆分、转换。
与 fund_transactions 分开存：这些事件不是买卖，不能参与 FIFO 成本与
已实现收益的计算；收益核对时叠加展示，不覆盖平台回执确认的份额。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8b1f30c95"
down_revision: Union[str, None] = "c9f3a7d82e14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fund_portfolio_flows",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="会员"),
        sa.Column("fund_id", sa.BigInteger(), nullable=False, comment="基金"),
        sa.Column("kind", sa.String(length=16), nullable=False, comment="事件类型"),
        sa.Column("effective_on", sa.Date(), nullable=False, comment="生效日期"),
        sa.Column("cash_amount", sa.Numeric(18, 2), nullable=True, comment="现金金额"),
        sa.Column("shares_delta", sa.Numeric(20, 4), nullable=True, comment="份额变动"),
        sa.Column("nav", sa.Numeric(16, 6), nullable=True, comment="事件净值"),
        sa.Column("ratio", sa.Numeric(10, 6), nullable=True, comment="拆分比例"),
        sa.Column("target_fund_id", sa.BigInteger(), nullable=True, comment="转换对手基金"),
        sa.Column("note", sa.String(length=200), nullable=True, comment="备注"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"]),
        sa.ForeignKeyConstraint(["target_fund_id"], ["funds.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="持仓补充流水：分红/再投/拆分/转换",
    )
    op.create_index(
        "ix_fund_portfolio_flows_user_id", "fund_portfolio_flows", ["user_id"]
    )
    op.create_index("ix_fund_portfolio_flows_fund_id", "fund_portfolio_flows", ["fund_id"])
    op.create_index(
        "ix_portfolio_flow_user_fund",
        "fund_portfolio_flows",
        ["user_id", "fund_id", "effective_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_flow_user_fund", table_name="fund_portfolio_flows")
    op.drop_index("ix_fund_portfolio_flows_fund_id", table_name="fund_portfolio_flows")
    op.drop_index("ix_fund_portfolio_flows_user_id", table_name="fund_portfolio_flows")
    op.drop_table("fund_portfolio_flows")
