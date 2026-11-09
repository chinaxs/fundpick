"""操作审计日志查询（仅超管）。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep, SuperUser
from app.repositories.audit_log import AuditLogRepository
from app.schemas.admin import AuditLogRead, AuditQuery
from app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/audit-logs", tags=["后台 · 审计"])


@router.get("", summary="操作日志", response_model=ApiResponse[PageResult[AuditLogRead]])
async def list_audit_logs(
    user: SuperUser,
    session: SessionDep,
    request_id: RequestIdDep,
    query: Annotated[AuditQuery, Query()] = None,  # type: ignore[assignment]
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[PageResult[AuditLogRead]]:
    rows, total = await AuditLogRepository(session).search(query or AuditQuery(), page, page_size)
    return ApiResponse(
        data=PageResult(
            items=[AuditLogRead.model_validate(row, from_attributes=True) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        ),
        request_id=request_id,
    )
