"""门户 · 我的关注（需登录）。

门户下的接口默认匿名只读，这一组是例外：必须登录才能访问。
之所以仍放在 `portal/`，是因为它服务的是门户会员而非后台运营，
身份用 `CurrentUser`（后台账号也可用，运营看自己的关注是合理需求）。
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, RequestIdDep, SessionDep
from app.schemas.common import ApiResponse, MessageResponse, PageResult
from app.schemas.favorite import FavoriteToggleRequest, FavoriteToggleResponse
from app.schemas.fund import FundListItem
from app.services.favorite import FavoriteService

router = APIRouter(prefix="/favorites", tags=["门户 · 自选"])


@router.get("", summary="我的关注列表", response_model=ApiResponse[PageResult[FundListItem]])
async def list_favorites(
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    period: Annotated[str, Query(description="指标区间")] = "1y",
) -> ApiResponse[PageResult[FundListItem]]:
    data = await FavoriteService(session).page(user.id, page, page_size, period)
    return ApiResponse(data=data, request_id=request_id)


@router.get("/codes", summary="已关注的基金代码", response_model=ApiResponse[list[str]])
async def favorite_codes(
    user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[list[str]]:
    """列表页用它一次性拿到全部已关注代码，避免逐行查询。"""
    data = await FavoriteService(session).codes(user.id)
    return ApiResponse(data=data, request_id=request_id)


@router.post(
    "",
    summary="关注基金",
    response_model=ApiResponse[FavoriteToggleResponse],
)
async def add_favorite(
    payload: FavoriteToggleRequest,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[FavoriteToggleResponse]:
    await FavoriteService(session).add(user.id, payload.code)
    return ApiResponse(
        message="已加入关注",
        data=FavoriteToggleResponse(code=payload.code, favorited=True),
        request_id=request_id,
    )


@router.delete(
    "/{code}",
    summary="取消关注",
    response_model=ApiResponse[FavoriteToggleResponse],
)
async def remove_favorite(
    code: str,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[FavoriteToggleResponse]:
    await FavoriteService(session).remove(user.id, code)
    return ApiResponse(
        message="已取消关注",
        data=FavoriteToggleResponse(code=code, favorited=False),
        request_id=request_id,
    )


@router.delete("", summary="清空关注", response_model=ApiResponse[MessageResponse])
async def clear_favorites(
    user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[MessageResponse]:
    """清空当前用户的全部关注。"""
    service = FavoriteService(session)
    for code in await service.codes(user.id):
        await service.remove(user.id, code)
    return ApiResponse(data=MessageResponse(message="已清空"), request_id=request_id)
