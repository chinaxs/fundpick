"""add feedback and password reset requests

Revision ID: b8d2e4c61f37
Revises: a7c3f1b9d502
Create Date: 2026-11-08

会员支持闭环：反馈工单 + 密码重置申请。
重置令牌只存 SHA-256 摘要；`token_hash` 为空表示"已申请、待客服核实"，
与"已生成链接"共用一张表，避免两套状态机。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2e4c61f37"
down_revision: Union[str, None] = "a7c3f1b9d502"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="提交会员"),
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default="other",
            comment="account / data / function / bug / other",
        ),
        sa.Column("title", sa.String(length=120), nullable=False, comment="标题"),
        sa.Column("content", sa.Text(), nullable=False, comment="描述"),
        sa.Column("contact", sa.String(length=120), nullable=True, comment="联系方式"),
        sa.Column("page_url", sa.String(length=255), nullable=True, comment="出问题的页面"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="open",
            comment="open / processing / resolved / closed",
        ),
        sa.Column("reply", sa.Text(), nullable=True, comment="公开回复"),
        sa.Column("handled_by", sa.String(length=50), nullable=True, comment="处理人快照"),
        sa.Column("handled_at", sa.DateTime(), nullable=True, comment="处理时间"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="会员反馈工单",
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_status", "feedback", ["status"])
    op.create_index("ix_feedback_status_created", "feedback", ["status", "created_at"])

    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="申请会员"),
        sa.Column("token_hash", sa.String(length=64), nullable=True, comment="令牌摘要"),
        sa.Column("expires_at", sa.DateTime(), nullable=True, comment="令牌过期时间"),
        sa.Column("used_at", sa.DateTime(), nullable=True, comment="使用时间"),
        sa.Column("requested_ip", sa.String(length=64), nullable=True, comment="申请来源 IP"),
        sa.Column("issued_by", sa.String(length=50), nullable=True, comment="生成链接的客服"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="申请时间",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="会员密码重置申请",
    )
    op.create_index(
        "ix_password_reset_requests_user_id", "password_reset_requests", ["user_id"]
    )
    op.create_index("ix_password_reset_user_created", "password_reset_requests", ["user_id", "created_at"])
    op.create_index(
        "ix_password_reset_requests_token_hash",
        "password_reset_requests",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_requests_token_hash", table_name="password_reset_requests")
    op.drop_index("ix_password_reset_user_created", table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_user_id", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
    op.drop_index("ix_feedback_status_created", table_name="feedback")
    op.drop_index("ix_feedback_status", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")
