"""后台 - 会员支持（反馈处理、密码重置、只读排查）。

这里的接口都在 `SuperUser` 之下：反馈里可能含个人信息，交易明细更敏感。
查看交易会写审计；不提供任何修改会员账本的入口。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import RequestIdDep, SessionDep, SuperUser
from app.schemas.common import ApiResponse, PageResult
from app.schemas.support import (
    FeedbackListItem,
    FeedbackRead,
    FeedbackUpdate,
    MemberPortfolioRead,
    MemberSupportRead,
    PasswordResetRead,
    ResetLinkRead,
)
from app.services.feedback import FeedbackService
from app.services.member_support import MemberSupportService
from app.services.password_reset import PasswordResetService

router = APIRouter(prefix="/support", tags=["后台 · 会员支持"])


# ---------------------------------------------------------------- 反馈
@router.get(
    "/feedback",
    summary="反馈工单列表",
    response_model=ApiResponse[PageResult[FeedbackListItem]],
)
async def list_feedback(
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query(max_length=20)] = None,
    category: Annotated[str | None, Query(max_length=20)] = None,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
) -> ApiResponse[PageResult[FeedbackListItem]]:
    items, total = await FeedbackService(session).list_admin(
        page=page,
        page_size=page_size,
        status=status,
        category=category,
        keyword=keyword,
    )
    return ApiResponse(
        data=PageResult[FeedbackListItem](items=items, total=total, page=page, page_size=page_size),
        request_id=request_id,
    )


@router.patch(
    "/feedback/{feedback_id}",
    summary="更新反馈状态与回复",
    response_model=ApiResponse[FeedbackRead],
)
async def update_feedback(
    feedback_id: int,
    payload: FeedbackUpdate,
    session: SessionDep,
    request_id: RequestIdDep,
    staff: SuperUser,
) -> ApiResponse[FeedbackRead]:
    feedback = await FeedbackService(session).update(feedback_id, payload, staff.username)
    return ApiResponse(data=feedback, request_id=request_id)


# ---------------------------------------------------------------- 密码重置
@router.get(
    "/password-resets",
    summary="密码重置申请",
    response_model=ApiResponse[list[PasswordResetRead]],
)
async def list_password_resets(
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
    status: Annotated[str | None, Query(pattern="^(pending|issued|used)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[PasswordResetRead]]:
    rows = await PasswordResetService(session).list_requests(status=status, limit=limit)
    return ApiResponse(data=rows, request_id=request_id)


@router.post(
    "/members/{user_id}/reset-link",
    summary="生成一次性密码重置链接",
    response_model=ApiResponse[ResetLinkRead],
)
async def create_reset_link(
    user_id: int,
    session: SessionDep,
    request_id: RequestIdDep,
    staff: SuperUser,
) -> ApiResponse[ResetLinkRead]:
    """令牌只在本次响应出现，关闭后无法再次查看；请当场发给会员本人。"""
    link = await PasswordResetService(session).issue_link(user_id, staff.username)
    return ApiResponse(data=link, request_id=request_id)


# ---------------------------------------------------------------- 会员排查
@router.get(
    "/members/{user_id}",
    summary="会员支持概览",
    response_model=ApiResponse[MemberSupportRead],
)
async def member_overview(
    user_id: int,
    session: SessionDep,
    request_id: RequestIdDep,
    _: SuperUser,
) -> ApiResponse[MemberSupportRead]:
    data = await MemberSupportService(session).overview(user_id)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/members/{user_id}/portfolio",
    summary="会员交易只读排查",
    response_model=ApiResponse[MemberPortfolioRead],
)
async def member_portfolio(
    user_id: int,
    request: Request,
    session: SessionDep,
    request_id: RequestIdDep,
    staff: SuperUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> ApiResponse[MemberPortfolioRead]:
    """只读：查看会写审计（谁、何时、看了谁的账本）。"""
    data = await MemberSupportService(session).portfolio(user_id, limit)
    await MemberSupportService(session).record_view(
        staff_id=staff.id,
        staff_username=staff.username,
        user_id=user_id,
        path=str(request.url.path),
        ip=request.client.host if request.client else None,
    )
    return ApiResponse(data=data, request_id=request_id)
