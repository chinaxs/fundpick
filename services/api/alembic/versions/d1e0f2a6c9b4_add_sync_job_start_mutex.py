"""Serialize synchronization task startup across API workers.

Revision ID: d1e0f2a6c9b4
Revises: c0d5a8e19b73
"""

import sqlalchemy as sa
from alembic import op

revision = "d1e0f2a6c9b4"
down_revision = "c0d5a8e19b73"
branch_labels = None
depends_on = None


def upgrade():
    mutex = op.create_table(
        "sync_job_mutex",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        comment="数据同步任务启动互斥锁",
    )
    op.bulk_insert(mutex, [{"id": 1}])


def downgrade():
    op.drop_table("sync_job_mutex")
