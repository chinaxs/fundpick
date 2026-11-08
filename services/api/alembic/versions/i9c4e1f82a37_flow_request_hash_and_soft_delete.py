"""add request hash and soft delete to portfolio flows

Revision ID: i9c4e1f82a37
Revises: h8b2d5e07c91
Create Date: 2026-11-09

公司行为的幂等键只校验"键相同"是不够的：同一个键换了金额还返回旧记录，
用户的新数字被静默丢弃；删除又是硬删除，旧请求重试会把记录重新入账。

`request_hash` 保存请求内容摘要，`deleted_at` 保留删除墓碑。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i9c4e1f82a37"
down_revision: Union[str, None] = "h8b2d5e07c91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fund_portfolio_flows",
        sa.Column("request_hash", sa.String(length=64), nullable=True, comment="请求内容摘要"),
    )
    op.add_column(
        "fund_portfolio_flows",
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间（墓碑）"),
    )
    op.create_index(
        "ix_fund_portfolio_flows_deleted_at", "fund_portfolio_flows", ["deleted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_fund_portfolio_flows_deleted_at", table_name="fund_portfolio_flows")
    op.drop_column("fund_portfolio_flows", "deleted_at")
    op.drop_column("fund_portfolio_flows", "request_hash")
