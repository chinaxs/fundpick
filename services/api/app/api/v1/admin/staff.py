"""后台 - 员工账号管理接口（staff_users 表，仅超管）。

与 `/admin/users`（门户会员管理）是两张独立的表：
这里增删的是"能登录后台的员工"，那边的对象是官网注册的会员。
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
from app.schemas.staff import StaffCreate, StaffQuery, StaffRead, StaffUpdate
from app.services.staff import StaffService

router = APIRouter(prefix="/staff", tags=["后台 · 员工"])


@router.post(
    "/batch-delete", summary="批量删除员工（软删除）", response_model=ApiResponse[BatchResult]
)
async def batch_delete_staff(
    payload: BatchIdsRequest,
    session: SessionDep,
    request_id: RequestIdDep,
    staff: SuperUser,
) -> ApiResponse[BatchResult]:
    # 操作者本人被排除，防止超管把自己删了把后台锁死
    affected = await StaffService(session).delete_many(payload.ids, exclude_id=staff.id)
    return ApiResponse(data=BatchResult(affected=affected), request_id=request_id)


@router.get("", summary="员工列表", response_model=ApiResponse[PageResult[StaffRead]])
async def list_staff(
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ApiResponse[PageResult[StaffRead]]:
    result = await StaffService(session).list(
        StaffQuery(keyword=keyword, is_active=is_active),
        PageParams(page=page, page_size=page_size),
    )
    return ApiResponse(
        data=PageResult[StaffRead](
            items=[StaffRead.model_validate(s) for s in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        ),
        request_id=request_id,
    )


@router.post("", summary="创建员工账号", response_model=ApiResponse[StaffRead], status_code=201)
async def create_staff(
    payload: StaffCreate, session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[StaffRead]:
    staff = await StaffService(session).create(payload)
    return ApiResponse(data=StaffRead.model_validate(staff), request_id=request_id)


@router.get("/{staff_id}", summary="员工详情", response_model=ApiResponse[StaffRead])
async def get_staff(
    staff_id: int, session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[StaffRead]:
    staff = await StaffService(session).get_or_404(staff_id)
    return ApiResponse(data=StaffRead.model_validate(staff), request_id=request_id)


@router.patch("/{staff_id}", summary="更新员工", response_model=ApiResponse[StaffRead])
async def update_staff(
    staff_id: int,
    payload: StaffUpdate,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[StaffRead]:
    staff = await StaffService(session).update(staff_id, payload, actor_id=_.id)
    return ApiResponse(data=StaffRead.model_validate(staff), request_id=request_id)


@router.delete("/{staff_id}", summary="删除员工（软删除）", response_model=ApiResponse[IdResponse])
async def delete_staff(
    staff_id: int, session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[IdResponse]:
    await StaffService(session).delete(staff_id, actor_id=_.id)
    return ApiResponse(data=IdResponse(id=staff_id), request_id=request_id)
