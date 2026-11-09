"""add simulated fund positions

Revision ID: e5a93c70d1b4
Revises: b7e21c04d93a
Create Date: 2026-11-06

会员模拟持仓：只录入买入金额与买入时净值，份额由两者相除得出。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5a93c70d1b4"
down_revision: Union[str, None] = "b7e21c04d93a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fund_positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="会员 ID"),
        sa.Column("fund_id", sa.BigInteger(), nullable=False, comment="基金 ID"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, comment="买入金额（元）"),
        sa.Column(
            "cost_nav", sa.Numeric(12, 4), nullable=False, comment="买入时单位净值（用于折算份额）"
        ),
        sa.Column("bought_at", sa.Date(), nullable=False, comment="模拟买入日期"),
        sa.Column("note", sa.String(200), nullable=True, comment="备注"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间（软删除）"),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="模拟持仓（会员自建，不涉及真实交易）",
    )
    op.create_index("ix_position_user_created", "fund_positions", ["user_id", "created_at"])
    op.create_index(op.f("ix_fund_positions_user_id"), "fund_positions", ["user_id"])
    op.create_index(op.f("ix_fund_positions_fund_id"), "fund_positions", ["fund_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_fund_positions_fund_id"), table_name="fund_positions")
    op.drop_index(op.f("ix_fund_positions_user_id"), table_name="fund_positions")
    op.drop_index("ix_position_user_created", table_name="fund_positions")
    op.drop_table("fund_positions")
