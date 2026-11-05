"""后台 - 文章管理接口。"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import RequestIdDep, SessionDep, StaffUser
from app.models.article import ArticleStatus
from app.schemas.article import ArticleCreate, ArticleListItem, ArticleRead, ArticleUpdate
from app.schemas.common import (
    ApiResponse,
    BatchIdsRequest,
    BatchResult,
    IdResponse,
    PageParams,
    PageResult,
)
from app.services.article import ArticleService

router = APIRouter(prefix="/articles", tags=["后台 · 内容"])


class BatchStatusRequest(BatchIdsRequest):
    """批量设置文章状态。"""

    status: ArticleStatus


@router.post(
    "/batch-delete", summary="批量删除文章（软删除）", response_model=ApiResponse[BatchResult]
)
async def batch_delete_articles(
    payload: BatchIdsRequest, session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[BatchResult]:
    affected = await ArticleService(session).delete_many(payload.ids)
    return ApiResponse(data=BatchResult(affected=affected), request_id=request_id)


@router.post(
    "/batch-status", summary="批量发布 / 撤回文章", response_model=ApiResponse[BatchResult]
)
async def batch_update_status(
    payload: BatchStatusRequest, session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[BatchResult]:
    affected = await ArticleService(session).update_status_many(payload.ids, payload.status)
    return ApiResponse(data=BatchResult(affected=affected), request_id=request_id)




@router.get("", summary="文章列表", response_model=ApiResponse[PageResult[ArticleListItem]])
async def list_articles(
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ArticleStatus | None = None,
    keyword: str | None = None,
) -> ApiResponse[PageResult[ArticleListItem]]:
    result = await ArticleService(session).list_admin(
        PageParams(page=page, page_size=page_size), status, keyword
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


@router.post("", summary="创建文章", response_model=ApiResponse[ArticleRead], status_code=201)
async def create_article(
    payload: ArticleCreate, session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[ArticleRead]:
    article = await ArticleService(session).create(payload)
    return ApiResponse(data=ArticleRead.model_validate(article), request_id=request_id)


@router.get("/{article_id}", summary="文章详情", response_model=ApiResponse[ArticleRead])
async def get_article(
    article_id: int, session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[ArticleRead]:
    article = await ArticleService(session).get_or_404(article_id)
    return ApiResponse(data=ArticleRead.model_validate(article), request_id=request_id)


@router.patch("/{article_id}", summary="更新文章", response_model=ApiResponse[ArticleRead])
async def update_article(
    article_id: int,
    payload: ArticleUpdate,
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
) -> ApiResponse[ArticleRead]:
    article = await ArticleService(session).update(article_id, payload)
    return ApiResponse(data=ArticleRead.model_validate(article), request_id=request_id)


@router.delete(
    "/{article_id}", summary="删除文章（软删除）", response_model=ApiResponse[IdResponse]
)
async def delete_article(
    article_id: int, session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[IdResponse]:
    await ArticleService(session).delete(article_id)
    return ApiResponse(data=IdResponse(id=article_id), request_id=request_id)
