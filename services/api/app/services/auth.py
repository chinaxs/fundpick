"""认证业务逻辑。

门户会员（users 表）与后台员工（staff_users 表）是两套完全独立的账号体系，
各自维护 login / refresh / change_password，但共享密码校验与令牌签发原语，
避免两边的密码策略、有效期悄悄漂移。

令牌通过 `scope` 声明归属（portal / staff），解码端强校验：
门户令牌调不动 `/admin/**`，员工令牌也不是门户会员。
"""

from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ValidationError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models.staff import StaffUser
from app.models.user import User
from app.repositories.staff import StaffUserRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse

Scope = Literal["portal", "staff"]


def issue_tokens(user_id: int, scope: Scope) -> TokenResponse:
    """签发一对令牌。两边账号都走这里，保证有效期一致。"""
    return TokenResponse(
        access_token=create_token(user_id, "access", scope=scope),
        refresh_token=create_token(user_id, "refresh", scope=scope),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _check_credentials(hashed: str | None, password: str) -> None:
    """统一提示，避免暴露账号是否存在。"""
    if hashed is None or not verify_password(password, hashed):
        raise UnauthorizedError("用户名或密码错误")


class AuthService:
    """门户会员认证（users 表）。"""

    scope: Scope = "portal"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def login(self, identifier: str, password: str) -> TokenResponse:
        user = await self.users.get_by_username_or_email(identifier)
        _check_credentials(user.hashed_password if user else None, password)
        assert user is not None  # 供类型检查收窄
        if not user.is_active:
            raise UnauthorizedError("账号已被禁用")
        # 与 MySQL now() 保持一致，统一使用本地时间
        user.last_login_at = datetime.now()
        await self.session.commit()
        return issue_tokens(user.id, self.scope)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type="refresh", expected_scope=self.scope)
        user = await self.users.get(int(payload["sub"]))
        if not user or not user.is_active:
            raise UnauthorizedError("账号不存在或已禁用")
        return issue_tokens(user.id, self.scope)

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.hashed_password):
            raise ValidationError("原密码不正确")
        user.hashed_password = hash_password(new_password)
        await self.session.commit()


class StaffAuthService:
    """后台员工认证（staff_users 表）。"""

    scope: Scope = "staff"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.staff = StaffUserRepository(session)

    async def login(self, identifier: str, password: str) -> TokenResponse:
        staff = await self.staff.get_by_username_or_email(identifier)
        _check_credentials(staff.hashed_password if staff else None, password)
        assert staff is not None  # 供类型检查收窄
        if not staff.is_active:
            raise UnauthorizedError("账号已被禁用")
        staff.last_login_at = datetime.now()
        await self.session.commit()
        return issue_tokens(staff.id, self.scope)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type="refresh", expected_scope=self.scope)
        staff = await self.staff.get(int(payload["sub"]))
        if not staff or not staff.is_active:
            raise UnauthorizedError("账号不存在或已禁用")
        return issue_tokens(staff.id, self.scope)

    async def change_password(
        self, staff: StaffUser, old_password: str, new_password: str
    ) -> None:
        if not verify_password(old_password, staff.hashed_password):
            raise ValidationError("原密码不正确")
        staff.hashed_password = hash_password(new_password)
        await self.session.commit()
