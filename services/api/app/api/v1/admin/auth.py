"""认证接口。"""

from fastapi import APIRouter

from app.api.deps import RequestIdDep, SessionDep, StaffUser
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.user import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["后台 · 认证"])


@router.post("/login", summary="账号密码登录", response_model=ApiResponse[TokenResponse])
async def login(
    payload: LoginRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[TokenResponse]:
    tokens = await AuthService(session).login(
        payload.username, payload.password, require_staff=True
    )
    return ApiResponse(code=0, message="登录成功", data=tokens, request_id=request_id)


@router.post("/refresh", summary="刷新令牌", response_model=ApiResponse[TokenResponse])
async def refresh(
    payload: RefreshRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[TokenResponse]:
    tokens = await AuthService(session).refresh(payload.refresh_token)
    return ApiResponse(data=tokens, request_id=request_id)


@router.get("/me", summary="获取当前登录用户", response_model=ApiResponse[UserRead])
async def me(user: StaffUser, request_id: RequestIdDep) -> ApiResponse[UserRead]:
    return ApiResponse(data=UserRead.model_validate(user), request_id=request_id)


@router.post("/change-password", summary="修改密码", response_model=ApiResponse[MessageResponse])
async def change_password(
    payload: ChangePasswordRequest,
    user: StaffUser,
    session: SessionDep,
    request_id: RequestIdDep,
) -> ApiResponse[MessageResponse]:
    await AuthService(session).change_password(user, payload.old_password, payload.new_password)
    return ApiResponse(data=MessageResponse(message="密码已更新"), request_id=request_id)
