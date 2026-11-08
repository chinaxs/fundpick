"""后台 - 基金管理与数据同步（需登录）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep, StaffUser, SuperUser
from app.schemas.common import ApiResponse, PageResult
from app.schemas.data_quality import DataQualityReport
from app.schemas.fund import FundListItem, FundQuery
from app.schemas.sync_job import (
    SyncAlert,
    SyncJobRead,
    SyncScheduleCreate,
    SyncScheduleRead,
    SyncScheduleUpdate,
    SyncTriggerRequest,
)
from app.services.data_quality import DataQualityService
from app.services.fund import FundService
from app.services.sync_job import SyncJobService
from app.services.sync_schedule import SyncScheduleService

router = APIRouter(prefix="/funds", tags=["后台 · 基金"])


@router.get(
    "/data-quality",
    summary="基金数据质量检查",
    response_model=ApiResponse[DataQualityReport],
)
async def data_quality(
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
) -> ApiResponse[DataQualityReport]:
    report = await DataQualityService(session).report(page, page_size, keyword)
    return ApiResponse(data=report, request_id=request_id)


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
    """给后台一个"数据是否新鲜"的直观指标（聚合值只读）。

    每次采集的执行记录见 `sync_jobs` 表（/funds/sync/jobs）。
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


# ---------------------------------------------------------------- 手动同步
@router.post("/sync", summary="立即同步（手动触发）", response_model=ApiResponse[SyncJobRead])
async def trigger_sync(
    payload: SyncTriggerRequest,
    session: SessionDep,
    request_id: RequestIdDep,
    staff: SuperUser,
) -> ApiResponse[SyncJobRead]:
    """点击后台「立即同步」按钮触发一次采集，任务在独立子进程执行。

    仅超管可触发；同一时间只允许一个任务运行。接口立即返回，
    前端用 /sync/jobs/{id} 轮询状态。审计中间件会自动记录操作人。
    """
    job = await SyncJobService(session).start(payload, staff.username)
    return ApiResponse(data=job, request_id=request_id)


@router.get("/sync/jobs", summary="同步任务历史", response_model=ApiResponse[list[SyncJobRead]])
async def list_sync_jobs(
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[SyncJobRead]]:
    jobs = await SyncJobService(session).list_recent(limit)
    return ApiResponse(data=jobs, request_id=request_id)


@router.get("/sync/jobs/{job_id}", summary="同步任务详情", response_model=ApiResponse[SyncJobRead])
async def get_sync_job(
    job_id: int,
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
) -> ApiResponse[SyncJobRead]:
    job = await SyncJobService(session).get(job_id)
    return ApiResponse(data=job, request_id=request_id)


@router.post(
    "/sync/jobs/{job_id}/cancel",
    summary="取消同步任务",
    response_model=ApiResponse[SyncJobRead],
)
async def cancel_sync_job(
    job_id: int,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[SyncJobRead]:
    """放取消标记，脚本在下个检查点退出；已结束的任务返回 409。"""
    job = await SyncJobService(session).cancel(job_id)
    return ApiResponse(data=job, request_id=request_id)


@router.post(
    "/sync/jobs/{job_id}/retry",
    summary="重试同步任务",
    response_model=ApiResponse[SyncJobRead],
)
async def retry_sync_job(
    job_id: int,
    session: SessionDep,
    request_id: RequestIdDep,
    staff: SuperUser,
) -> ApiResponse[SyncJobRead]:
    """用历史任务的模式与参数创建新任务，原记录保持不可变。"""
    job = await SyncJobService(session).retry(job_id, staff.username)
    return ApiResponse(data=job, request_id=request_id)


@router.get("/sync/alerts", summary="同步任务告警", response_model=ApiResponse[list[SyncAlert]])
async def sync_alerts(
    session: SessionDep,
    request_id: RequestIdDep,
    _: StaffUser,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> ApiResponse[list[SyncAlert]]:
    rows = await SyncJobService(session).alerts(hours)
    return ApiResponse(data=[SyncAlert(**row) for row in rows], request_id=request_id)


# ---------------------------------------------------------------- 定时调度
@router.get(
    "/sync/schedules",
    summary="采集定时配置",
    response_model=ApiResponse[list[SyncScheduleRead]],
)
async def list_sync_schedules(
    session: SessionDep, request_id: RequestIdDep, _: StaffUser
) -> ApiResponse[list[SyncScheduleRead]]:
    rows = await SyncScheduleService(session).list()
    return ApiResponse(data=rows, request_id=request_id)


@router.post(
    "/sync/schedules",
    summary="新增采集定时",
    response_model=ApiResponse[SyncScheduleRead],
)
async def create_sync_schedule(
    payload: SyncScheduleCreate,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[SyncScheduleRead]:
    row = await SyncScheduleService(session).create(payload)
    return ApiResponse(data=row, request_id=request_id)


@router.patch(
    "/sync/schedules/{schedule_id}",
    summary="调整采集定时",
    response_model=ApiResponse[SyncScheduleRead],
)
async def update_sync_schedule(
    schedule_id: int,
    payload: SyncScheduleUpdate,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[SyncScheduleRead]:
    row = await SyncScheduleService(session).update(schedule_id, payload)
    return ApiResponse(data=row, request_id=request_id)


@router.delete("/sync/schedules/{schedule_id}", summary="删除采集定时")
async def delete_sync_schedule(
    schedule_id: int,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[None]:
    await SyncScheduleService(session).delete(schedule_id)
    return ApiResponse(data=None, request_id=request_id)
