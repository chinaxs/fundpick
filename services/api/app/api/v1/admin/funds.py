"""后台 - 基金管理（需登录）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep, StaffUser
from app.schemas.common import ApiResponse, PageResult
from app.schemas.fund import FundListItem, FundQuery
from app.services.fund import FundService

router = APIRouter(prefix="/funds", tags=["后台 · 基金"])


@router.get("", summary="基金列表", response_model=ApiResponse[PageResult[FundListItem]])
async def list_funds(
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
    query: Annotated[FundQuery, Query()],
) -> ApiResponse[PageResult[FundListItem]]:
    result = await FundService(session).search(query)
    return ApiResponse(data=result, request_id=request_id)


@router.get("/sync-status", summary="数据同步概况", response_model=ApiResponse[dict])
async def sync_status(
    session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[dict]:
    """给后台一个"数据是否新鲜"的直观指标。

    正式版应改读一张 sync_jobs 表（记录每次采集的开始/结束/条数/错误），
    这里先返回可用的聚合值。
    """
    from sqlalchemy import func, select

    from app.models.fund import Fund
    from app.models.fund_nav import FundNav

    total = (await session.execute(select(func.count()).select_from(Fund))).scalar_one()
    latest_nav_date = (await session.execute(select(func.max(Fund.latest_nav_date)))).scalar_one()
    nav_rows = (await session.execute(select(func.count()).select_from(FundNav))).scalar_one()

    return ApiResponse(
        data={
            "fund_total": int(total),
            "nav_rows": int(nav_rows),
            "latest_nav_date": latest_nav_date.isoformat() if latest_nav_date else None,
        },
        request_id=request_id,
    )
