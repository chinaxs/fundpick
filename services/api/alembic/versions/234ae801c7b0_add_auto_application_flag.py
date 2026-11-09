"""Only retry applications explicitly created for automatic calculation.
Revision ID: 234ae801c7b0
Revises: 17a64ef8cb90
"""
import sqlalchemy as sa
from alembic import op
revision = "234ae801c7b0"
down_revision = "17a64ef8cb90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trade_applications", sa.Column("automatic_processing", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("trade_applications", "automatic_processing")
