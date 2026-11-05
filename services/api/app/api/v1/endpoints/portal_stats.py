"""门户 - 聚合统计（公开接口）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.stats import OverviewStats, ReturnDistribution
from app.services.fund import FundService

router = APIRouter(prefix="/portal/stats", tags=["门户-统计"])


@router.get("/overview", summary="市场概览", response_model=ApiResponse[OverviewStats])
async def overview(session: SessionDep, request_id: RequestIdDep) -> ApiResponse[OverviewStats]:
    """首页顶部数据与类型分布。"""
    data = await FundService(session).overview_stats()
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/return-distribution",
    summary="区间收益分布",
    response_model=ApiResponse[ReturnDistribution],
)
async def return_distribution(
    session: SessionDep,
    request_id: RequestIdDep,
    period: str = Query(default="1y", description="1w/1m/3m/6m/1y/3y/ytd/all"),
) -> ApiResponse[ReturnDistribution]:
    """全市场区间收益分布，用于首页直方图。"""
    data = await FundService(session).return_distribution(period)
    return ApiResponse(data=data, request_id=request_id)
