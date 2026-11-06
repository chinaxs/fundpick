"""FastAPI 依赖注入：会话、当前用户、权限校验。

两套账号体系、两条鉴权链路：

- `CurrentUser` —— 门户会员（users 表，令牌 scope=portal），
  供门户自选、会员信息等接口使用；
- `StaffUser` —— 后台员工（staff_users 表，令牌 scope=staff），
  供 `/admin/**` 全部接口使用；`SuperUser` 在此基础上要求超管。

令牌里的 scope 是第一道闸：即使两表主键撞号，令牌也解不出对方的身份。
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_session
from app.models.staff import StaffUser as StaffUserModel
from app.models.user import User
from app.repositories.staff import StaffUserRepository
from app.repositories.user import UserRepository

# ---- 数据库会话 ----
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---- 请求上下文 ----
def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


RequestIdDep = Annotated[str, Depends(get_request_id)]

# ---- 认证 ----
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer <access_token>")
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _decode_access(credentials: BearerDep, scope: str) -> dict:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError()
    try:
        return decode_token(credentials.credentials, expected_type="access", expected_scope=scope)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc


async def get_current_user(request: Request, session: SessionDep, credentials: BearerDep) -> User:
    """门户会员：令牌必须由 /portal/auth 签发（scope=portal）。"""
    payload = _decode_access(credentials, scope="portal")

    user = await UserRepository(session).get(int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("账号不存在或已被禁用")

    # 供审计中间件识别操作人（中间件在 call_next 之后读取）
    request.state.user_id = user.id
    request.state.username = user.username
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_staff(
    request: Request, session: SessionDep, credentials: BearerDep
) -> StaffUserModel:
    """后台员工：令牌必须由 /admin/auth 签发（scope=staff）。"""
    payload = _decode_access(credentials, scope="staff")

    staff = await StaffUserRepository(session).get(int(payload["sub"]))
    if staff is None or not staff.is_active:
        raise UnauthorizedError("账号不存在或已被禁用")

    # 供审计中间件识别操作人（中间件在 call_next 之后读取）
    request.state.user_id = staff.id
    request.state.username = staff.username
    return staff


StaffUser = Annotated[StaffUserModel, Depends(get_current_staff)]


async def get_current_superuser(staff: StaffUser) -> StaffUserModel:
    if not staff.is_superuser:
        raise ForbiddenError("需要管理员权限")
    return staff


SuperUser = Annotated[StaffUserModel, Depends(get_current_superuser)]
