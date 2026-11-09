"""Persist automatic posting attempts and fee-parser cache version.

Revision ID: l3f7b5c9e012
Revises: k2e6a4b8d901
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "l3f7b5c9e012"
down_revision: str | None = "k2e6a4b8d901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trade_applications", sa.Column("last_attempt_at", sa.DateTime(), nullable=True))
    op.add_column("trade_applications", sa.Column("next_retry_at", sa.DateTime(), nullable=True))
    op.create_index("ix_trade_applications_next_retry_at", "trade_applications", ["next_retry_at"])
    op.add_column("fund_fee_schedules", sa.Column("parser_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("fund_fee_schedules", "parser_version")
    op.drop_index("ix_trade_applications_next_retry_at", table_name="trade_applications")
    op.drop_column("trade_applications", "next_retry_at")
    op.drop_column("trade_applications", "last_attempt_at")
