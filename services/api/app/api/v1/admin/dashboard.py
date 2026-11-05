"""后台仪表盘与系统信息。"""

from fastapi import APIRouter

from app.api.deps import RequestIdDep, SessionDep, StaffUser, SuperUser
from app.schemas.admin import DashboardOverview, SystemInfo
from app.schemas.common import ApiResponse
from app.services.admin_stats import AdminStatsService

router = APIRouter(tags=["后台 · 概览"])


@router.get(
    "/dashboard",
    summary="运营概览",
    response_model=ApiResponse[DashboardOverview],
)
async def dashboard(
    user: StaffUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[DashboardOverview]:
    """一次返回首页所需的全部聚合数据，避免前端并发打多个接口。"""
    data = await AdminStatsService(session).dashboard()
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/system/info",
    summary="系统信息（仅超管）",
    response_model=ApiResponse[SystemInfo],
)
async def system_info(
    user: SuperUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[SystemInfo]:
    data = await AdminStatsService(session).system_info()
    return ApiResponse(data=data, request_id=request_id)
