"""add sync jobs table

Revision ID: a1c7e95b3d20
Revises: f2b71d4e9c30
Create Date: 2026-11-06

后台「立即同步」按钮的任务记录表。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c7e95b3d20"
down_revision: Union[str, None] = "f2b71d4e9c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mode", sa.String(32), nullable=False, comment="同步模式"),
        sa.Column("params", sa.String(255), nullable=True, comment="参数 JSON"),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="running",
            comment="running/success/failed",
        ),
        sa.Column("triggered_by", sa.String(50), nullable=True, comment="触发人（后台账号）"),
        sa.Column("pid", sa.Integer(), nullable=True, comment="子进程 PID"),
        sa.Column("log_file", sa.String(255), nullable=True, comment="日志文件相对名"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("log_tail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="数据同步任务记录",
    )
    op.create_index(op.f("ix_sync_jobs_mode"), "sync_jobs", ["mode"])
    op.create_index(op.f("ix_sync_jobs_status"), "sync_jobs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_jobs_status"), table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_mode"), table_name="sync_jobs")
    op.drop_table("sync_jobs")
