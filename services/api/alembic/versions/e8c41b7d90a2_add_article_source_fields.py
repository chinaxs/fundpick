"""add article source fields

Revision ID: e8c41b7d90a2
Revises: d5a2f7c41e08
Create Date: 2026-11-07

后台一键同步资讯快讯所需字段。外部资讯只保存标题、摘要、来源与原文链接，
不保存正文；external_id 唯一，保证重复同步不会产生重复文章。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8c41b7d90a2"
down_revision: Union[str, None] = "d5a2f7c41e08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("source", sa.String(length=32), nullable=True, comment="来源标识"),
    )
    op.add_column(
        "articles",
        sa.Column("source_name", sa.String(length=50), nullable=True, comment="来源展示名"),
    )
    op.add_column(
        "articles",
        sa.Column("source_url", sa.String(length=500), nullable=True, comment="原文链接"),
    )
    op.add_column(
        "articles",
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default="market",
            comment="分类：policy / market / company / other",
        ),
    )
    op.add_column(
        "articles",
        sa.Column(
            "origin",
            sa.String(length=20),
            nullable=False,
            server_default="manual",
            comment="manual 人工撰写 / sync 外部同步",
        ),
    )
    op.add_column(
        "articles",
        sa.Column("external_id", sa.String(length=64), nullable=True, comment="外部资讯指纹"),
    )
    op.create_index("ix_articles_category", "articles", ["category"])
    op.create_index("ix_articles_external_id", "articles", ["external_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_articles_external_id", table_name="articles")
    op.drop_index("ix_articles_category", table_name="articles")
    op.drop_column("articles", "external_id")
    op.drop_column("articles", "origin")
    op.drop_column("articles", "category")
    op.drop_column("articles", "source_url")
    op.drop_column("articles", "source_name")
    op.drop_column("articles", "source")
