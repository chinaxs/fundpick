"""Track risk metric baseline date and source.

Revision ID: c0d5a8e19b73
Revises: 34f0b7a9d812
"""

import sqlalchemy as sa
from alembic import op

revision = "c0d5a8e19b73"
down_revision = "34f0b7a9d812"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "fund_metrics",
        sa.Column("risk_nav_date", sa.Date(), nullable=True, comment="风险指标基准日"),
    )
    op.add_column(
        "fund_metrics",
        sa.Column("risk_source", sa.String(length=80), nullable=True, comment="风险指标数据来源"),
    )


def downgrade():
    op.drop_column("fund_metrics", "risk_source")
    op.drop_column("fund_metrics", "risk_nav_date")
