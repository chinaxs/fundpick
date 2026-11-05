"""门户内容示例模型（文章 / 资讯）。"""

from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Article(TimestampMixin, SoftDeleteMixin, Base):
    """门户网站资讯文章，供后台维护、门户展示。"""

    __tablename__ = "articles"
    __table_args__: ClassVar[dict[str, str]] = {"comment": "文章表"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="标题")
    slug: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True, comment="URL 标识"
    )
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="摘要")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="正文（Markdown）")
    cover_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="封面图")
    status: Mapped[ArticleStatus] = mapped_column(
        # values_callable：存枚举的 value（draft/published/archived）而非 name，
        # 与接口契约、前端类型保持一致
        Enum(
            ArticleStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ArticleStatus.DRAFT,
        server_default=ArticleStatus.DRAFT.value,
        index=True,
        comment="状态",
    )
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="浏览量"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True, comment="发布时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article id={self.id} slug={self.slug!r} status={self.status}>"
