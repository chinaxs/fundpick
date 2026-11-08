"""后台 - 运行健康度（仅超管）。

不做"一键备份"按钮：备份要拿数据库凭据、写磁盘、还要考虑复制到别处，
放在 API 进程里点一下就把权限和资源边界搞乱了。后台只展示状态和命令。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import RequestIdDep, SessionDep, SuperUser
from app.schemas.common import ApiResponse
from app.schemas.ops import OpsStatus
from app.services.ops_health import OpsHealthService

router = APIRouter(prefix="/system", tags=["后台 · 概览"])


@router.get("/health", summary="运行健康度", response_model=ApiResponse[OpsStatus])
async def ops_health(
    session: SessionDep, request_id: RequestIdDep, _: SuperUser
) -> ApiResponse[OpsStatus]:
    data = await OpsHealthService(session).status()
    return ApiResponse(data=data, request_id=request_id)
