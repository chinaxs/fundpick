"""文章仓储。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.models.article import Article, ArticleStatus
from app.repositories.base import BaseRepository
from app.schemas.common import PageParams, PageResult


class ArticleRepository(BaseRepository[Article]):
    model = Article

    async def get_by_slug(self, slug: str) -> Article | None:
        return await self.get_by(slug=slug)

    async def slug_exists(self, slug: str, exclude_id: int | None = None) -> bool:
        stmt = select(Article.id).where(Article.slug == slug, Article.deleted_at.is_(None))
        if exclude_id:
            stmt = stmt.where(Article.id != exclude_id)
        return (await self.session.execute(stmt.limit(1))).scalar_one_or_none() is not None

    async def published(
        self, params: PageParams, keyword: str | None = None
    ) -> PageResult[Article]:
        stmt = self._base_stmt().where(
            Article.status == ArticleStatus.PUBLISHED,
            Article.published_at.is_not(None),
            Article.published_at <= datetime.now(),
        )
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(Article.title.like(like), Article.summary.like(like)))
        stmt = stmt.order_by(Article.published_at.desc())
        return await self.paginate(stmt, params)

    async def stats(self) -> dict[str, int]:
        """文章总量与已发布数量（供 AI 工具 / 仪表盘使用）。"""
        base = select(func.count()).select_from(Article).where(Article.deleted_at.is_(None))
        total = (await self.session.execute(base)).scalar_one()
        published = (
            await self.session.execute(base.where(Article.status == ArticleStatus.PUBLISHED))
        ).scalar_one()
        return {"total": int(total), "published": int(published)}

    async def admin_list(
        self, params: PageParams, status: ArticleStatus | None = None, keyword: str | None = None
    ) -> PageResult[Article]:
        stmt = self._base_stmt()
        if status:
            stmt = stmt.where(Article.status == status)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(Article.title.like(like))
        stmt = stmt.order_by(Article.id.desc())
        return await self.paginate(stmt, params)
