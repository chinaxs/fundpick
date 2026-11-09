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

from app.core.exceptions import UnauthorizedError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.staff import StaffUser
from app.models.user import User
from app.repositories.staff import StaffUserRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.auth_sessions import (
    finish_refresh,
    issue_tokens,
    revoke_all_for_account,
    rotate_refresh_token,
)
from app.services.login_limiter import (
    check_login_allowed,
    clear_login_failures,
    login_key,
    record_login_failure,
)

Scope = Literal["portal", "staff"]


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

    async def login(
        self, identifier: str, password: str, client_ip: str | None = None
    ) -> TokenResponse:
        attempt_key = login_key(self.scope, identifier, client_ip)
        await check_login_allowed(self.session, attempt_key)
        user = await self.users.get_by_username_or_email(identifier)
        try:
            _check_credentials(user.hashed_password if user else None, password)
        except UnauthorizedError:
            await record_login_failure(self.session, attempt_key)
            raise
        assert user is not None  # 供类型检查收窄
        await clear_login_failures(self.session, attempt_key)
        if not user.is_active:
            raise UnauthorizedError("账号已被禁用")
        # 与 MySQL now() 保持一致，统一使用本地时间
        user.last_login_at = datetime.now()
        await self.session.commit()
        return await issue_tokens(self.session, user.id, self.scope)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        auth_session, user_id = await rotate_refresh_token(self.session, refresh_token, self.scope)
        user = await self.users.get(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("账号不存在或已禁用")
        return await finish_refresh(self.session, auth_session, user.id, self.scope)

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.hashed_password):
            raise ValidationError("原密码不正确")
        user.hashed_password = hash_password(new_password)
        await revoke_all_for_account(self.session, self.scope, user.id)
        await self.session.commit()


class StaffAuthService:
    """后台员工认证（staff_users 表）。"""

    scope: Scope = "staff"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.staff = StaffUserRepository(session)

    async def login(
        self, identifier: str, password: str, client_ip: str | None = None
    ) -> TokenResponse:
        attempt_key = login_key(self.scope, identifier, client_ip)
        await check_login_allowed(self.session, attempt_key)
        staff = await self.staff.get_by_username_or_email(identifier)
        try:
            _check_credentials(staff.hashed_password if staff else None, password)
        except UnauthorizedError:
            await record_login_failure(self.session, attempt_key)
            raise
        assert staff is not None  # 供类型检查收窄
        await clear_login_failures(self.session, attempt_key)
        if not staff.is_active:
            raise UnauthorizedError("账号已被禁用")
        staff.last_login_at = datetime.now()
        await self.session.commit()
        return await issue_tokens(self.session, staff.id, self.scope)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        auth_session, staff_id = await rotate_refresh_token(self.session, refresh_token, self.scope)
        staff = await self.staff.get(staff_id)
        if not staff or not staff.is_active:
            raise UnauthorizedError("账号不存在或已禁用")
        return await finish_refresh(self.session, auth_session, staff.id, self.scope)

    async def change_password(self, staff: StaffUser, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, staff.hashed_password):
            raise ValidationError("原密码不正确")
        staff.hashed_password = hash_password(new_password)
        await revoke_all_for_account(self.session, self.scope, staff.id)
        await self.session.commit()
