"""Delete cancelled/voided records from member history while keeping idempotency tombstones.
Revision ID: 34f0b7a9d812
Revises: 234ae801c7b0
"""

import sqlalchemy as sa
from alembic import op

revision = "34f0b7a9d812"
down_revision = "234ae801c7b0"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("fund_transactions", "trade_applications"):
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.create_index(
            f"ix_{table}_history", table, ["user_id", "deleted_at", "submitted_at", "id"]
        )


def downgrade():
    for table in ("fund_transactions", "trade_applications"):
        op.drop_index(f"ix_{table}_history", table_name=table)
        op.drop_column(table, "deleted_at")
