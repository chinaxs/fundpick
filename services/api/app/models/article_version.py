"""文章版本记录。

每次保存都追加一行快照（append-only），用于回答"发布前改了什么"，
并支持把任意历史版本恢复成一个**新版本**——历史本身不被覆盖。

为什么存整份内容而不是 diff：文章正文通常几 KB，整份快照让恢复逻辑
只有一条 UPDATE，不会出现"补丁套补丁"还原不回去的情况。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArticleVersion(Base):
    __tablename__ = "article_versions"
    __table_args__ = (
        Index("ix_article_version_article", "article_id", "version"),
        {"comment": "文章版本快照"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("articles.id"), nullable=False, index=True, comment="文章"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号（从 1 递增）")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="标题快照")
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="摘要快照")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="正文快照")
    category: Mapped[str] = mapped_column(String(20), nullable=False, comment="分类快照")
    source_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="来源名")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="原文链接")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="保存时的状态")
    edited_by: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="保存人（后台账号快照）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="保存时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ArticleVersion article={self.article_id} v{self.version}>"
