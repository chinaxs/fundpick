"""门户 - 会员自助（个人中心 / 工作台），全部需要登录。

沿用 favorites.py 的先例：会员专属接口放在 /portal/** 下，
但用 CurrentUser 注入令牌（scope=portal），OpenAPI tag 标明需登录。
写操作仅作用于当前登录会员自己，不接收 user_id 参数，杜绝越权。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, RequestIdDep, SessionDep
from app.schemas.auth import ChangePasswordRequest
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.portal_auth import PortalUserRead
from app.schemas.portal_me import (
    DashboardResponse,
    PasswordConfirm,
    ProfileUpdateRequest,
)
from app.services.portal_me import PortalMeService

router = APIRouter(prefix="/me", tags=["门户 · 会员中心（需登录）"])


@router.get("/dashboard", summary="我的工作台统计", response_model=ApiResponse[DashboardResponse])
async def dashboard(
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
    period: str = Query(default="1y", description="收益统计区间"),
) -> ApiResponse[DashboardResponse]:
    """一次返回关注基金的汇总、分布、收益榜与最近关注。"""
    data = await PortalMeService(session).dashboard(user.id, period)
    return ApiResponse(data=data, request_id=request_id)


@router.patch("", summary="更新我的资料", response_model=ApiResponse[PortalUserRead])
async def update_profile(
    payload: ProfileUpdateRequest,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[PortalUserRead]:
    """只允许改邮箱 / 显示名称 / 头像，用户名与状态不可改。"""
    updated = await PortalMeService(session).update_profile(user, payload)
    return ApiResponse(data=PortalUserRead.model_validate(updated), request_id=request_id)


@router.post(
    "/change-password", summary="修改密码", response_model=ApiResponse[MessageResponse]
)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[MessageResponse]:
    """校验原密码后更新；JWT 无状态，已签发的令牌继续有效至过期。"""
    await PortalMeService(session).change_password(user, payload.old_password, payload.new_password)
    return ApiResponse(data=MessageResponse(message="密码已更新"), request_id=request_id)


@router.post("/deactivate", summary="注销账号", response_model=ApiResponse[MessageResponse])
async def deactivate(
    payload: PasswordConfirm,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[MessageResponse]:
    """二次校验密码后软删账号并清除关注，当前令牌随即失效。"""
    await PortalMeService(session).deactivate(user, payload.password)
    return ApiResponse(data=MessageResponse(message="账号已注销"), request_id=request_id)
