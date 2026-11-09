"""add sync task center fields and schedule table

Revision ID: a7c3f1b9d502
Revises: f2a90c71d4e6
Create Date: 2026-11-08

采集任务中心：任务行增加阶段、计数、失败明细、心跳、取消与超时字段，
并新增 `sync_schedules` 定时配置表。计数由采集脚本的进度文件回填，
因此列都带非空默认值，历史任务不需要回填脚本。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3f1b9d502"
down_revision: Union[str, None] = "f2a90c71d4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "sync_jobs",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.add_column(
        "sync_jobs",
        sa.Column("phase", sa.String(length=32), nullable=True, comment="当前阶段"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("total", sa.Integer(), nullable=False, server_default="0", comment="目标数"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0", comment="成功数"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0", comment="失败数"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0", comment="跳过数"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("failures", sa.Text(), nullable=True, comment="失败明细 JSON"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True, comment="进度心跳"),
    )
    op.add_column(
        "sync_jobs",
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="已请求取消",
        ),
    )
    op.add_column(
        "sync_jobs",
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="1800",
            comment="超时秒数",
        ),
    )

    op.create_table(
        "sync_schedules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, comment="同步模式"),
        sa.Column("hour", sa.Integer(), nullable=False, comment="小时 0-23"),
        sa.Column("minute", sa.Integer(), nullable=False, comment="分钟 0-59"),
        sa.Column(
            "weekdays",
            sa.String(length=20),
            nullable=False,
            server_default="1,2,3,4,5",
            comment="ISO 星期，1=周一",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column("last_run_on", sa.Date(), nullable=True, comment="最近触发日期"),
        sa.Column("last_job_id", sa.BigInteger(), nullable=True, comment="最近产生的任务"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="数据同步定时配置",
    )


def downgrade() -> None:
    op.drop_table("sync_schedules")
    op.drop_column("sync_jobs", "timeout_seconds")
    op.drop_column("sync_jobs", "cancel_requested")
    op.drop_column("sync_jobs", "heartbeat_at")
    op.drop_column("sync_jobs", "failures")
    op.drop_column("sync_jobs", "skipped")
    op.drop_column("sync_jobs", "failed")
    op.drop_column("sync_jobs", "succeeded")
    op.drop_column("sync_jobs", "total")
    op.drop_column("sync_jobs", "phase")
    op.alter_column(
        "sync_jobs",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
