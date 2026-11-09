"""Separate applications, NAV day and actual receipt confirmation.

Revision ID: 0b8d37c91f20
Revises: f9c61d72ab30
"""

import sqlalchemy as sa
from alembic import op

revision = "0b8d37c91f20"
down_revision = "f9c61d72ab30"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trade_applications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fund_id", sa.BigInteger(), sa.ForeignKey("funds.id"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("expected_nav_on", sa.Date(), nullable=True),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("pricing_rule", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("shares", sa.Numeric(20, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "request_key", name="uq_application_request"),
    )
    op.create_index("ix_trade_applications_user_id", "trade_applications", ["user_id"])
    for column in (
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("settled_on", sa.Date(), nullable=True),
        sa.Column("platform", sa.String(80), nullable=True),
        sa.Column("receipt_ref", sa.String(100), nullable=True),
        sa.Column("record_source", sa.String(16), nullable=False, server_default="calculated"),
        sa.Column("pricing_rule", sa.String(16), nullable=True),
        sa.Column("date_reason", sa.String(200), nullable=True),
        sa.Column("application_id", sa.BigInteger(), nullable=True),
    ):
        op.add_column("fund_transactions", column)
    op.create_foreign_key(
        "fk_transaction_application",
        "fund_transactions",
        "trade_applications",
        ["application_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_transaction_application", "fund_transactions", ["application_id"]
    )


def downgrade():
    op.drop_constraint("fk_transaction_application", "fund_transactions", type_="foreignkey")
    op.drop_constraint("uq_transaction_application", "fund_transactions", type_="unique")
    for name in (
        "application_id",
        "date_reason",
        "pricing_rule",
        "record_source",
        "receipt_ref",
        "platform",
        "settled_on",
        "submitted_at",
    ):
        op.drop_column("fund_transactions", name)
    op.drop_table("trade_applications")
