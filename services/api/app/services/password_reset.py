"""会员密码重置。

仓库里没有邮件服务，所以流程刻意不伪装"已发送邮件"：

1. 会员在门户提交注册邮箱或登录名 → 生成一条**待核实**记录（不含令牌）；
2. 客服在后台核实身份后生成一次性链接，线下发给本人；
3. 会员打开链接设置新密码 → 令牌立即失效，该账号全部会话被撤销。

令牌只存 SHA-256 摘要，泄露数据库也无法用于重置；有效期 30 分钟、用完即弃。
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.support import PasswordResetRequest
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.support import PasswordResetRead, ResetLinkRead
from app.services.auth_sessions import revoke_all_for_account

RESET_TTL_MINUTES = 30
# 同一会员 10 分钟内最多提交几次申请，避免被用来刷工单
REQUEST_WINDOW_MINUTES = 10
REQUEST_LIMIT = 3


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PasswordResetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def request(self, account: str, client_ip: str | None = None) -> None:
        """提交重置申请。

        无论账号是否存在都返回成功（避免枚举注册邮箱），
        只有真实存在的账号才会落一条待处理记录。
        """
        user = await self.users.get_by_username_or_email(account.strip())
        if user is None or not user.is_active:
            return
        since = datetime.now() - timedelta(minutes=REQUEST_WINDOW_MINUTES)
        recent = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(PasswordResetRequest)
                    .where(
                        PasswordResetRequest.user_id == user.id,
                        PasswordResetRequest.created_at >= since,
                    )
                )
            ).scalar_one()
            or 0
        )
        if recent >= REQUEST_LIMIT:
            return
        self.session.add(PasswordResetRequest(user_id=user.id, requested_ip=client_ip))
        await self.session.commit()

    async def issue_link(self, user_id: int, staff_username: str) -> ResetLinkRead:
        """客服生成一次性链接：令牌只在这里出现一次，之后无法再取回。"""
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("会员不存在")
        if not user.is_active:
            raise ValidationError("会员已被禁用，不能重置密码")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=RESET_TTL_MINUTES)
        # 收回仍有效的旧链接，重新生成的链接是当前唯一可用凭证。
        now = datetime.now()
        await self.session.execute(
            update(PasswordResetRequest)
            .where(
                PasswordResetRequest.user_id == user_id,
                PasswordResetRequest.token_hash.is_not(None),
                PasswordResetRequest.used_at.is_(None),
            )
            .values(expires_at=now - timedelta(seconds=1))
        )
        pending = (
            (
                await self.session.execute(
                    select(PasswordResetRequest)
                    .where(
                        PasswordResetRequest.user_id == user_id,
                        PasswordResetRequest.token_hash.is_(None),
                        PasswordResetRequest.used_at.is_(None),
                    )
                    .order_by(PasswordResetRequest.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if pending:
            request = pending[-1]
            request.token_hash = _digest(token)
            request.expires_at = expires_at
            request.issued_by = staff_username
            # 重复申请已由此次核实处理，退出待办列表。
            for earlier in pending[:-1]:
                earlier.used_at = now
        else:
            self.session.add(
                PasswordResetRequest(
                    user_id=user.id,
                    token_hash=_digest(token),
                    expires_at=expires_at,
                    issued_by=staff_username,
                )
            )
        await self.session.commit()
        return ResetLinkRead(
            user_id=user.id,
            username=user.username,
            token=token,
            expires_at=expires_at,
            path=f"/reset-password?token={token}",
        )

    async def reset(self, token: str, new_password: str) -> int:
        """用令牌设置新密码，返回会员 ID。"""
        # 先锁账号再锁链接，与 issue_link 保持同一锁顺序；回收链接与重置串行。
        owner_id = await self.session.scalar(
            select(PasswordResetRequest.user_id).where(
                PasswordResetRequest.token_hash == _digest(token)
            )
        )
        if owner_id is None:
            raise ValidationError("重置链接无效或已使用")
        await self.session.execute(select(User.id).where(User.id == owner_id).with_for_update())
        request = (
            await self.session.execute(
                select(PasswordResetRequest)
                .where(PasswordResetRequest.token_hash == _digest(token))
                .with_for_update()
            )
        ).scalar_one_or_none()
        now = datetime.now()
        if request is None or request.used_at is not None:
            raise ValidationError("重置链接无效或已使用")
        if request.expires_at is None or request.expires_at <= now:
            raise ValidationError("重置链接已过期，请重新申请")

        user = await self.users.get(request.user_id)
        if user is None or not user.is_active:
            raise ValidationError("账号不存在或已禁用")

        user.hashed_password = hash_password(new_password)
        request.used_at = now
        # 保留 token_hash 摘要用于追溯"哪条链接被用过"；重复提交会因 used_at 被拒
        await revoke_all_for_account(self.session, "portal", user.id)
        await self.session.commit()
        return user.id

    async def list_requests(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[PasswordResetRead]:
        stmt = select(PasswordResetRequest, User).join(
            User, User.id == PasswordResetRequest.user_id, isouter=True
        )
        if status == "pending":
            stmt = stmt.where(
                PasswordResetRequest.token_hash.is_(None),
                PasswordResetRequest.used_at.is_(None),
            )
        elif status == "issued":
            stmt = stmt.where(
                PasswordResetRequest.token_hash.is_not(None),
                PasswordResetRequest.used_at.is_(None),
            )
        elif status == "used":
            stmt = stmt.where(PasswordResetRequest.used_at.is_not(None))
        rows = (
            await self.session.execute(stmt.order_by(PasswordResetRequest.id.desc()).limit(limit))
        ).all()
        return [
            PasswordResetRead(
                id=request.id,
                user_id=request.user_id,
                username=user.username if user else None,
                email=user.email if user else None,
                requested_ip=request.requested_ip,
                created_at=request.created_at,
                used_at=request.used_at,
                expires_at=request.expires_at,
                issued_by=request.issued_by,
                pending=request.pending,
            )
            for request, user in rows
        ]
