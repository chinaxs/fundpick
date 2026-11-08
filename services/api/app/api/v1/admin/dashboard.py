"""后台仪表盘与系统信息。"""

from fastapi import APIRouter

from app.api.deps import RequestIdDep, SessionDep, StaffUser, SuperUser
from app.schemas.admin import DashboardOverview, EngagementSummary, SystemInfo
from app.schemas.common import ApiResponse
from app.services.admin_stats import AdminStatsService
from app.services.engagement import EngagementService

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
    "/dashboard/engagement",
    summary="运营效果指标",
    response_model=ApiResponse[EngagementSummary],
)
async def engagement(
    user: StaffUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[EngagementSummary]:
    """活跃、回访、留存与转化。

    与 /dashboard 分开：这里的查询要扫会话表，没必要跟着每分钟的
    概览刷新一起跑。
    """
    data = await EngagementService(session).summary()
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
