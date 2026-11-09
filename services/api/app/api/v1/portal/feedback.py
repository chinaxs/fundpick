"""门户 - 会员反馈（需登录）。

反馈是会员与运营之间唯一的公开通道：个人资料页、关于页都指向这里，
后台在「会员支持」里处理并回复，会员回本页能看到处理结果。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, RequestIdDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.support import FeedbackCreate, FeedbackRead
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/feedback", tags=["门户 · 反馈"])


@router.post("", summary="提交反馈", response_model=ApiResponse[FeedbackRead], status_code=201)
async def create_feedback(
    payload: FeedbackCreate,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[FeedbackRead]:
    feedback = await FeedbackService(session).create(user.id, payload)
    return ApiResponse(code=0, message="已收到，感谢反馈", data=feedback, request_id=request_id)


@router.get("", summary="我的反馈", response_model=ApiResponse[list[FeedbackRead]])
async def list_my_feedback(
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ApiResponse[list[FeedbackRead]]:
    rows = await FeedbackService(session).list_mine(user.id, limit)
    return ApiResponse(data=rows, request_id=request_id)
