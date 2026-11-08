"""门户会员认证接口。

与后台 `/admin/auth/**` 完全独立：账号存在 users 表（后台员工在 staff_users 表），
签发的令牌带 scope=portal，拿去调 `/admin/**` 会在依赖层被拒。
"""

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, RequestIdDep, SessionDep
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.portal_auth import PortalUserRead, RegisterRequest
from app.schemas.support import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_sessions import revoke_from_refresh
from app.services.password_reset import PasswordResetService
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
    payload: LoginRequest, session: SessionDep, request_id: RequestIdDep, request: Request
) -> ApiResponse[TokenResponse]:
    client_ip = request.client.host if request.client else None
    tokens = await PortalAuthService(session).login(payload.username, payload.password, client_ip)
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
async def logout(
    payload: RefreshRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[MessageResponse]:
    await revoke_from_refresh(session, payload.refresh_token, "portal")
    return ApiResponse(data=MessageResponse(message="已退出登录"), request_id=request_id)


@router.post(
    "/forgot-password",
    summary="申请重置密码",
    response_model=ApiResponse[MessageResponse],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: SessionDep,
    request_id: RequestIdDep,
    request: Request,
) -> ApiResponse[MessageResponse]:
    """提交重置申请。

    无论账号是否存在都返回同样的提示，避免被用来枚举注册邮箱；
    当前没有邮件服务，客服核实身份后会线下把一次性链接发给本人。
    """
    client_ip = request.client.host if request.client else None
    await PasswordResetService(session).request(payload.account, client_ip)
    return ApiResponse(
        data=MessageResponse(
            message="已收到申请。客服核实身份后会通过你留存的联系方式发送重置链接。"
        ),
        request_id=request_id,
    )


@router.post(
    "/reset-password",
    summary="用链接重置密码",
    response_model=ApiResponse[MessageResponse],
)
async def reset_password(
    payload: ResetPasswordRequest, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[MessageResponse]:
    """令牌一次性使用；成功后该账号全部会话失效，需要重新登录。"""
    await PasswordResetService(session).reset(payload.token, payload.new_password)
    return ApiResponse(
        data=MessageResponse(message="密码已重置，请用新密码登录"),
        request_id=request_id,
    )
