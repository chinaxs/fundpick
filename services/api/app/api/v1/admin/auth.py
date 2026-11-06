"""后台认证接口（staff_users 表）。"""

from fastapi import APIRouter, Request

from app.api.deps import RequestIdDep, SessionDep, StaffUser
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.staff import StaffRead
from app.services.auth import StaffAuthService

router = APIRouter(prefix="/auth", tags=["后台 · 认证"])


@router.post("/login", summary="账号密码登录", response_model=ApiResponse[TokenResponse])
async def login(
    payload: LoginRequest, session: SessionDep, request_id: RequestIdDep, request: Request
) -> ApiResponse[TokenResponse]:
    tokens = await StaffAuthService(session).login(payload.username, payload.password)
    # 登录成功后回填身份，供审计中间件把"谁登录了"写进日志
    request.state.username = payload.username
    return ApiResponse(code=0, message="登录成功", data=tokens, request_id=request_id)


@router.post("/refresh", summary="刷新令牌", response_model=ApiResponse[TokenResponse])
async def refresh(
    payload: RefreshRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[TokenResponse]:
    tokens = await StaffAuthService(session).refresh(payload.refresh_token)
    return ApiResponse(data=tokens, request_id=request_id)


@router.get("/me", summary="获取当前登录员工", response_model=ApiResponse[StaffRead])
async def me(user: StaffUser, request_id: RequestIdDep) -> ApiResponse[StaffRead]:
    return ApiResponse(data=StaffRead.model_validate(user), request_id=request_id)


@router.post("/change-password", summary="修改密码", response_model=ApiResponse[MessageResponse])
async def change_password(
    payload: ChangePasswordRequest,
    user: StaffUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[MessageResponse]:
    await StaffAuthService(session).change_password(user, payload.old_password, payload.new_password)
    return ApiResponse(data=MessageResponse(message="密码已更新"), request_id=request_id)
