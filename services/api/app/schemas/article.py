"""文章相关 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.article import ArticleStatus

# 与前端 ARTICLE_CATEGORY_MAP 保持一致
ARTICLE_CATEGORIES = ("policy", "market", "company", "other")


class ArticleBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200, description="留空则由标题自动生成")
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = None
    cover_url: str | None = None
    category: str = Field(
        default="market", max_length=20, description="policy/market/company/other"
    )
    source_name: str | None = Field(default=None, max_length=50, description="转载时的来源名")
    source_url: str | None = Field(default=None, max_length=500, description="转载时的原文链接")


class ArticleCreate(ArticleBase):
    status: ArticleStatus = ArticleStatus.DRAFT


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = None
    summary: str | None = None
    content: str | None = None
    cover_url: str | None = None
    status: ArticleStatus | None = None
    category: str | None = None
    source_name: str | None = None
    source_url: str | None = None


class ArticleRead(ArticleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ArticleStatus
    view_count: int
    published_at: datetime | None = None
    source: str | None = None
    origin: str = "manual"
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
    category: str = "market"
    source: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    origin: str = "manual"


class ArticleVersionRead(BaseModel):
    """历史版本快照（只读）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    version: int
    title: str
    summary: str | None = None
    content: str | None = None
    category: str
    source_name: str | None = None
    source_url: str | None = None
    status: str
    edited_by: str | None = None
    created_at: datetime
