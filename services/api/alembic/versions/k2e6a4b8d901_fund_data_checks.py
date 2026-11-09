"""Persist on-demand fund data refresh attempts.

Revision ID: k2e6a4b8d901
Revises: j1d5f3a9c84b
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k2e6a4b8d901"
down_revision: str | None = "j1d5f3a9c84b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fund_data_checks",
        sa.Column("fund_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("message", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fund_id", "kind"),
    )


def downgrade() -> None:
    op.drop_table("fund_data_checks")
