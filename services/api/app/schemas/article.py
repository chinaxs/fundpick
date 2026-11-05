"""文章相关 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.article import ArticleStatus


class ArticleBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200, description="留空则由标题自动生成")
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = None
    cover_url: str | None = None


class ArticleCreate(ArticleBase):
    status: ArticleStatus = ArticleStatus.DRAFT


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = None
    summary: str | None = None
    content: str | None = None
    cover_url: str | None = None
    status: ArticleStatus | None = None


class ArticleRead(ArticleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ArticleStatus
    view_count: int
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ArticleListItem(BaseModel):
    """列表页精简字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    summary: str | None = None
    cover_url: str | None = None
    status: ArticleStatus
    view_count: int
    published_at: datetime | None = None
