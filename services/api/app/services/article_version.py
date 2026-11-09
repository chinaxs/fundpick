"""文章版本仓储与业务逻辑。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.article import Article
from app.models.article_version import ArticleVersion


class ArticleVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_version(self, article_id: int) -> int:
        latest = (
            await self.session.execute(
                select(ArticleVersion.version)
                .where(ArticleVersion.article_id == article_id)
                .order_by(ArticleVersion.version.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        return int(latest or 0) + 1

    async def list_for(self, article_id: int, limit: int = 30) -> list[ArticleVersion]:
        rows = (
            await self.session.execute(
                select(ArticleVersion)
                .where(ArticleVersion.article_id == article_id)
                .order_by(ArticleVersion.version.desc())
                .limit(limit)
            )
        ).scalars()
        return list(rows)

    async def get(self, article_id: int, version: int) -> ArticleVersion | None:
        return (
            await self.session.execute(
                select(ArticleVersion).where(
                    ArticleVersion.article_id == article_id,
                    ArticleVersion.version == version,
                )
            )
        ).scalar_one_or_none()


class ArticleVersionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.versions = ArticleVersionRepository(session)

    async def snapshot(self, article: Article, editor: str | None) -> ArticleVersion:
        """保存一次快照（调用方负责 commit）。"""
        version = ArticleVersion(
            article_id=article.id,
            version=await self.versions.next_version(article.id),
            title=article.title,
            summary=article.summary,
            content=article.content,
            category=article.category,
            source_name=article.source_name,
            source_url=article.source_url,
            status=article.status.value
            if hasattr(article.status, "value")
            else str(article.status),
            edited_by=editor,
        )
        self.session.add(version)
        return version

    async def list(self, article_id: int, limit: int = 30) -> list[ArticleVersion]:
        return await self.versions.list_for(article_id, limit)

    async def restore(self, article: Article, version: int, editor: str | None) -> Article:
        """把历史版本写回文章，并追加一条新版本（历史保持不可变）。"""
        target = await self.versions.get(article.id, version)
        if target is None:
            raise NotFoundError("版本不存在")
        article.title = target.title
        article.summary = target.summary
        article.content = target.content
        article.category = target.category
        article.source_name = target.source_name
        article.source_url = target.source_url
        await self.snapshot(article, editor)
        return article


__all__ = ["ArticleVersionRepository", "ArticleVersionService"]
