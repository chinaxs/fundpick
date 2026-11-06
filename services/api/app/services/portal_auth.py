"""门户会员认证业务逻辑。

与后台认证完全独立的两套账号体系：

1. **注册写 users 表** —— 门户注册的账号在 staff_users 表里根本不存在，
   天然登不进后台；
2. **令牌 scope=portal** —— 即使有人拿门户令牌去调 `/admin/**`，
   也会被依赖层的 scope 校验拦下（401），双重隔离。

其余（令牌签发、密码校验、刷新）复用 `AuthService`，避免两套逻辑漂移。
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.portal_auth import RegisterRequest
from app.services.auth import AuthService, issue_tokens


class PortalAuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> TokenResponse:
        """注册并直接登录（降低首屏转化摩擦）。"""
        if await self.users.exists(username=payload.username):
            raise ConflictError("用户名已被占用")
        if payload.email and await self.users.exists(email=payload.email):
            raise ConflictError("该邮箱已注册")

        user = await self.users.create(
            username=payload.username,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            is_active=True,
            last_login_at=datetime.now(),
        )
        await self.session.commit()
        await self.session.refresh(user)
        return issue_tokens(user.id, "portal")

    async def login(self, identifier: str, password: str) -> TokenResponse:
        return await AuthService(self.session).login(identifier, password)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        return await AuthService(self.session).refresh(refresh_token)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.users.get(user_id)
