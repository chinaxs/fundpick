"""Persist auth sessions and login rate-limit windows.

Revision ID: f2a90c71d4e6
Revises: e3b74d1a9c20
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a90c71d4e6"
down_revision = "e3b74d1a9c20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Index("ix_auth_sessions_owner", "scope", "subject_id"),
        sa.Index("ix_auth_sessions_expiry", "expires_at"),
        comment="门户与后台登录会话",
    )
    op.create_table(
        "auth_login_attempts",
        sa.Column("key_hash", sa.String(length=64), primary_key=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        comment="按账号与来源限制登录失败次数",
    )


def downgrade():
    op.drop_table("auth_login_attempts")
    op.drop_table("auth_sessions")
