"""Persist public fee schedules and automatic calculation provenance.

Revision ID: 17a64ef8cb90
Revises: 0b8d37c91f20
"""

import sqlalchemy as sa
from alembic import op

revision = "17a64ef8cb90"
down_revision = "0b8d37c91f20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fund_fee_schedules",
        sa.Column("fund_id", sa.BigInteger(), sa.ForeignKey("funds.id"), primary_key=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(300), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.add_column(
        "trade_applications", sa.Column("processing_message", sa.String(500), nullable=True)
    )
    op.add_column("fund_transactions", sa.Column("calculation_basis", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("fund_transactions", "calculation_basis")
    op.drop_column("trade_applications", "processing_message")
    op.drop_table("fund_fee_schedules")
