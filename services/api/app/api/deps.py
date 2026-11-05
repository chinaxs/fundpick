"""FastAPI 依赖注入：会话、当前用户、权限校验。"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User
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


async def get_current_user(session: SessionDep, credentials: BearerDep) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError()
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user = await UserRepository(session).get(int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("账号不存在或已被禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise ForbiddenError("需要管理员权限")
    return user


SuperUser = Annotated[User, Depends(get_current_superuser)]
