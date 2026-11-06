"""后台 - 门户会员管理接口（users 表）。

注意：这里管理的是**官网注册的会员**，不是后台员工；
后台员工账号在 `/admin/staff`（staff_users 表）。
"""

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep, SuperUser
from app.schemas.common import (
    ApiResponse,
    BatchIdsRequest,
    BatchResult,
    IdResponse,
    PageParams,
    PageResult,
)
from app.schemas.user import UserCreate, UserQuery, UserRead, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["后台 · 用户"])


@router.post(
    "/batch-delete", summary="批量删除用户（软删除）", response_model=ApiResponse[BatchResult]
)
async def batch_delete_users(
    payload: BatchIdsRequest,
    session: SessionDep,
    request_id: RequestIdDep,
    user: SuperUser,
) -> ApiResponse[BatchResult]:
    # 操作者本人被排除，防止超管把自己删了把后台锁死
    affected = await UserService(session).delete_many(payload.ids, exclude_id=user.id)
    return ApiResponse(data=BatchResult(affected=affected), request_id=request_id)


@router.get("", summary="用户列表", response_model=ApiResponse[PageResult[UserRead]])
async def list_users(
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ApiResponse[PageResult[UserRead]]:
    result = await UserService(session).list(
        UserQuery(keyword=keyword, is_active=is_active),
        PageParams(page=page, page_size=page_size),
    )
    return ApiResponse(
        data=PageResult[UserRead](
            items=[UserRead.model_validate(u) for u in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        ),
        request_id=request_id,
    )


@router.post("", summary="创建用户", response_model=ApiResponse[UserRead], status_code=201)
async def create_user(
    payload: UserCreate, session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[UserRead]:
    user = await UserService(session).create(payload)
    return ApiResponse(data=UserRead.model_validate(user), request_id=request_id)


@router.get("/{user_id}", summary="用户详情", response_model=ApiResponse[UserRead])
async def get_user(
    user_id: int, session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[UserRead]:
    user = await UserService(session).get_or_404(user_id)
    return ApiResponse(data=UserRead.model_validate(user), request_id=request_id)


@router.patch("/{user_id}", summary="更新用户", response_model=ApiResponse[UserRead])
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[UserRead]:
    user = await UserService(session).update(user_id, payload)
    return ApiResponse(data=UserRead.model_validate(user), request_id=request_id)


@router.delete("/{user_id}", summary="删除用户（软删除）", response_model=ApiResponse[IdResponse])
async def delete_user(
    user_id: int, session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[IdResponse]:
    await UserService(session).delete(user_id)
    return ApiResponse(data=IdResponse(id=user_id), request_id=request_id)
