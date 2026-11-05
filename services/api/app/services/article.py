"""文章业务逻辑。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.article import Article, ArticleStatus
from app.repositories.article import ArticleRepository
from app.schemas.article import ArticleCreate, ArticleUpdate
from app.schemas.common import PageParams, PageResult
from app.utils.text import slugify


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.articles = ArticleRepository(session)

    async def get_or_404(self, article_id: int) -> Article:
        article = await self.articles.get(article_id)
        if not article:
            raise NotFoundError("文章不存在")
        return article

    async def get_published_by_slug(self, slug: str, *, count_view: bool = True) -> Article:
        """读取已发布文章。

        count_view=False 用于内部调用（如 AI 工具），避免机器阅读污染浏览统计。
        """
        article = await self.articles.get_by_slug(slug)
        if not article or article.status != ArticleStatus.PUBLISHED:
            raise NotFoundError("文章不存在或未发布")

        if not count_view:
            return article

        article.view_count += 1
        await self.session.commit()
        # updated_at 由数据库 onupdate 生成，commit 后属性过期，异步下必须显式刷新
        await self.session.refresh(article)
        return article

    async def stats(self) -> dict[str, int]:
        return await self.articles.stats()

    async def _ensure_unique_slug(self, slug: str, exclude_id: int | None = None) -> str:
        """slug 冲突时自动追加序号。"""
        candidate, index = slug, 1
        while await self.articles.slug_exists(candidate, exclude_id):
            index += 1
            candidate = f"{slug}-{index}"
        return candidate

    async def create(self, payload: ArticleCreate) -> Article:
        slug = await self._ensure_unique_slug(payload.slug or slugify(payload.title))
        article = await self.articles.create(
            **payload.model_dump(exclude={"slug"}),
            slug=slug,
            published_at=datetime.now() if payload.status == ArticleStatus.PUBLISHED else None,
        )
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def update(self, article_id: int, payload: ArticleUpdate) -> Article:
        article = await self.get_or_404(article_id)
        data = payload.model_dump(exclude_unset=True)

        if data.get("slug") and data["slug"] != article.slug:
            data["slug"] = await self._ensure_unique_slug(data["slug"], exclude_id=article_id)
        if data.get("status") == ArticleStatus.PUBLISHED and not article.published_at:
            data["published_at"] = datetime.now()

        await self.articles.update(article, **data)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def delete(self, article_id: int) -> None:
        article = await self.get_or_404(article_id)
        await self.articles.delete(article, soft=True)
        await self.session.commit()

    async def delete_many(self, ids: list[int]) -> int:
        """批量软删除，返回实际删除数。"""
        affected = await self.articles.update_many(ids, deleted_at=datetime.now())
        await self.session.commit()
        return affected

    async def update_status_many(self, ids: list[int], status: ArticleStatus) -> int:
        """批量发布 / 撤回。首次发布补 published_at。"""
        values: dict[str, object] = {"status": status}
        if status == ArticleStatus.PUBLISHED:
            values["published_at"] = datetime.now()
        affected = await self.articles.update_many(ids, **values)
        await self.session.commit()
        return affected

    async def list_published(
        self, params: PageParams, keyword: str | None = None
    ) -> PageResult[Article]:
        return await self.articles.published(params, keyword)

    async def list_admin(
        self,
        params: PageParams,
        status: ArticleStatus | None = None,
        keyword: str | None = None,
    ) -> PageResult[Article]:
        return await self.articles.admin_list(params, status, keyword)
