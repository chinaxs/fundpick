"""Serialize changes that can remove the final active superuser.

Revision ID: e3b74d1a9c20
Revises: d1e0f2a6c9b4
"""

import sqlalchemy as sa
from alembic import op

revision = "e3b74d1a9c20"
down_revision = "d1e0f2a6c9b4"
branch_labels = None
depends_on = None


def upgrade():
    mutex = op.create_table(
        "staff_admin_mutex",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        comment="超级管理员资格变更互斥锁",
    )
    op.bulk_insert(mutex, [{"id": 1}])


def downgrade():
    op.drop_table("staff_admin_mutex")
