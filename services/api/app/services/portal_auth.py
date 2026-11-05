"""门户会员认证业务逻辑。

与后台认证只差两点：

1. **注册出的账号 `is_staff=False`** —— 门户注册绝不能进后台，
   配合 `/admin/**` 的 `StaffUser` 依赖形成两道闸。
2. **登录不要求后台身份** —— 任何启用状态的账号都能登门户（后台账号也行，
   运营自己看前台数据是合理需求）。

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
            # 关键：门户注册的账号不是后台账号
            is_staff=False,
            is_superuser=False,
            last_login_at=datetime.now(),
        )
        await self.session.commit()
        await self.session.refresh(user)
        return issue_tokens(user)

    async def login(self, identifier: str, password: str) -> TokenResponse:
        # require_staff 默认 False：门户不限制账号类型
        return await AuthService(self.session).login(identifier, password)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        return await AuthService(self.session).refresh(refresh_token)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.users.get(user_id)
