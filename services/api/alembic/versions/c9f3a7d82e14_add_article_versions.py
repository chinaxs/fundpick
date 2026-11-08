"""add article versions

Revision ID: c9f3a7d82e14
Revises: b8d2e4c61f37
Create Date: 2026-11-08

文章版本快照：每次保存追加一行，支持查看与恢复历史。
恢复不删除历史，只追加新版本，保证"谁在何时改回什么"可追溯。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9f3a7d82e14"
down_revision: Union[str, None] = "b8d2e4c61f37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=False, comment="文章"),
        sa.Column("version", sa.Integer(), nullable=False, comment="版本号"),
        sa.Column("title", sa.String(length=200), nullable=False, comment="标题快照"),
        sa.Column("summary", sa.String(length=500), nullable=True, comment="摘要快照"),
        sa.Column("content", sa.Text(), nullable=True, comment="正文快照"),
        sa.Column("category", sa.String(length=20), nullable=False, comment="分类快照"),
        sa.Column("source_name", sa.String(length=50), nullable=True, comment="来源名"),
        sa.Column("source_url", sa.String(length=500), nullable=True, comment="原文链接"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="保存时状态"),
        sa.Column("edited_by", sa.String(length=50), nullable=True, comment="保存人"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="保存时间",
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="文章版本快照",
    )
    op.create_index("ix_article_versions_article_id", "article_versions", ["article_id"])
    op.create_index(
        "ix_article_version_article", "article_versions", ["article_id", "version"]
    )


def downgrade() -> None:
    op.drop_index("ix_article_version_article", table_name="article_versions")
    op.drop_index("ix_article_versions_article_id", table_name="article_versions")
    op.drop_table("article_versions")
