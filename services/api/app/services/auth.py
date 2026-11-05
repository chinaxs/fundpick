"""认证业务逻辑。"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ValidationError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse


def issue_tokens(user: User) -> TokenResponse:
    """签发一对令牌。后台与门户的登录都走这里，保证有效期一致。"""
    return TokenResponse(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def authenticate(
        self, identifier: str, password: str, *, require_staff: bool = False
    ) -> User:
        user = await self.users.get_by_username_or_email(identifier)
        # 统一提示，避免暴露账号是否存在
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("用户名或密码错误")
        if not user.is_active:
            raise UnauthorizedError("账号已被禁用")
        # 门户会员也持有有效 JWT，如果不在这里拦住，他们能登入后台。
        # 提示与密码错误保持一致，不泄露"该账号不是后台账号"。
        if require_staff and not (user.is_staff or user.is_superuser):
            raise UnauthorizedError("用户名或密码错误")
        return user

    async def login(
        self, identifier: str, password: str, *, require_staff: bool = False
    ) -> TokenResponse:
        user = await self.authenticate(identifier, password, require_staff=require_staff)
        # 与 MySQL now() 保持一致，统一使用本地时间
        user.last_login_at = datetime.now()
        await self.session.commit()
        return self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self.users.get(int(payload["sub"]))
        if not user or not user.is_active:
            raise UnauthorizedError("账号不存在或已禁用")
        return self._issue_tokens(user)

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.hashed_password):
            raise ValidationError("原密码不正确")
        user.hashed_password = hash_password(new_password)
        await self.session.commit()

    @staticmethod
    def _issue_tokens(user: User) -> TokenResponse:
        return issue_tokens(user)
