"""门户会员认证接口。

与后台 `/admin/auth/**` 完全独立：这边的账号 `is_staff=False`，
拿到的 token 调不动 `/admin/**`（由 `StaffUser` 依赖拦截）。
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, RequestIdDep, SessionDep
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.portal_auth import PortalUserRead, RegisterRequest
from app.services.portal_auth import PortalAuthService

router = APIRouter(prefix="/auth", tags=["门户 · 会员"])


@router.post(
    "/register",
    summary="注册会员",
    response_model=ApiResponse[TokenResponse],
)
async def register(
    payload: RegisterRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[TokenResponse]:
    """注册成功后直接返回令牌，前端可省略一次登录请求。"""
    tokens = await PortalAuthService(session).register(payload)
    return ApiResponse(code=0, message="注册成功", data=tokens, request_id=request_id)


@router.post("/login", summary="会员登录", response_model=ApiResponse[TokenResponse])
async def login(
    payload: LoginRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[TokenResponse]:
    tokens = await PortalAuthService(session).login(payload.username, payload.password)
    return ApiResponse(code=0, message="登录成功", data=tokens, request_id=request_id)


@router.post("/refresh", summary="刷新令牌", response_model=ApiResponse[TokenResponse])
async def refresh(
    payload: RefreshRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[TokenResponse]:
    tokens = await PortalAuthService(session).refresh(payload.refresh_token)
    return ApiResponse(code=0, data=tokens, request_id=request_id)


@router.get("/me", summary="当前会员", response_model=ApiResponse[PortalUserRead])
async def me(user: CurrentUser, request_id: RequestIdDep) -> ApiResponse[PortalUserRead]:
    return ApiResponse(data=PortalUserRead.model_validate(user), request_id=request_id)


@router.post("/logout", summary="退出登录", response_model=ApiResponse[MessageResponse])
async def logout(request_id: RequestIdDep) -> ApiResponse[MessageResponse]:
    """退出登录。

    JWT 是无状态的，服务端不保存会话，因此这里只做语义确认：
    客户端丢弃令牌即可。若要实现"立即失效"，需要引入令牌黑名单（如 Redis）。
    """
    return ApiResponse(data=MessageResponse(message="已退出登录"), request_id=request_id)
