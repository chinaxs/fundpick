"""Add confirmed simulated trade ledger; existing positions stay available for review.

Revision ID: f9c61d72ab30
Revises: e8c41b7d90a2
"""

import sqlalchemy as sa
from alembic import op

revision = "f9c61d72ab30"
down_revision = "e8c41b7d90a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fund_id", sa.BigInteger(), sa.ForeignKey("funds.id"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confirmed_on", sa.Date(), nullable=False),
        sa.Column("nav", sa.Numeric(16, 6), nullable=False),
        sa.Column("nav_source", sa.String(16), nullable=False),
        *[
            sa.Column(n, sa.Numeric(18, 2), nullable=False)
            for n in ("amount", "fee", "cash_amount", "realized_profit", "remaining_cost")
        ],
        *[sa.Column(n, sa.Numeric(20, 4), nullable=False) for n in ("shares", "remaining_shares")],
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "legacy_position_id",
            sa.BigInteger(),
            sa.ForeignKey("fund_positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("void_reason", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "request_key", name="uq_transaction_request"),
        comment="模拟买卖流水，作废保留审计记录",
    )
    op.create_index(
        "ix_transaction_user_fund_date",
        "fund_transactions",
        ["user_id", "fund_id", "confirmed_on", "id"],
    )


def downgrade() -> None:
    op.drop_table("fund_transactions")
