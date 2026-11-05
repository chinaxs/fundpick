"""门户 - 公开接口（无需登录）。"""

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep
from app.schemas.article import ArticleListItem, ArticleRead
from app.schemas.common import ApiResponse, PageParams, PageResult
from app.services.article import ArticleService

router = APIRouter(prefix="/portal/articles", tags=["门户-内容"])


@router.get("", summary="已发布文章列表", response_model=ApiResponse[PageResult[ArticleListItem]])
async def list_published(
    session: SessionDep,
    request_id: RequestIdDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    keyword: str | None = None,
) -> ApiResponse[PageResult[ArticleListItem]]:
    result = await ArticleService(session).list_published(
        PageParams(page=page, page_size=page_size), keyword
    )
    return ApiResponse(
        data=PageResult[ArticleListItem](
            items=[ArticleListItem.model_validate(a) for a in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        ),
        request_id=request_id,
    )


@router.get("/{slug}", summary="文章详情（按 slug）", response_model=ApiResponse[ArticleRead])
async def get_by_slug(
    slug: str, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[ArticleRead]:
    article = await ArticleService(session).get_published_by_slug(slug)
    return ApiResponse(data=ArticleRead.model_validate(article), request_id=request_id)
