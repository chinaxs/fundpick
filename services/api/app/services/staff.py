"""后台员工账号业务逻辑（staff_users 表）。"""

from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.staff import StaffAdminMutex, StaffUser
from app.repositories.staff import StaffUserRepository
from app.schemas.common import PageParams, PageResult
from app.schemas.staff import StaffCreate, StaffQuery, StaffUpdate
from app.services.auth_sessions import revoke_all_for_account, revoke_sessions_for_accounts


class StaffService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.staff = StaffUserRepository(session)

    async def get_or_404(self, staff_id: int) -> StaffUser:
        staff = await self.staff.get(staff_id)
        if not staff:
            raise NotFoundError("员工账号不存在")
        return staff

    async def create(self, payload: StaffCreate) -> StaffUser:
        if await self.staff.exists(username=payload.username):
            raise ConflictError("用户名已存在")
        if payload.email and await self.staff.exists(email=payload.email):
            raise ConflictError("邮箱已被占用")

        staff = await self.staff.create(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            is_superuser=payload.is_superuser,
        )
        await self.session.commit()
        await self.session.refresh(staff)
        return staff

    async def list(self, query: StaffQuery, params: PageParams) -> PageResult[StaffUser]:
        return await self.staff.search(query, params)

    async def update(
        self, staff_id: int, payload: StaffUpdate, *, actor_id: int | None = None
    ) -> StaffUser:
        data = payload.model_dump(exclude_unset=True)
        if "is_active" in data or "is_superuser" in data:
            await self._lock_admin_membership()
        staff = await self.get_or_404(staff_id)

        if (
            actor_id is not None
            and actor_id == staff_id
            and (data.get("is_active") is False or data.get("is_superuser") is False)
        ):
            raise ConflictError("不能禁用自己或移除自己的超级管理员权限")

        removes_access = (
            staff.is_active
            and staff.is_superuser
            and (data.get("is_active") is False or data.get("is_superuser") is False)
        )
        if removes_access:
            await self._require_another_active_superuser(staff_id)

        if "email" in data and data["email"] and await self.staff.exists(email=data["email"]):
            existing = await self.staff.get_by(email=data["email"])
            if existing and existing.id != staff_id:
                raise ConflictError("邮箱已被占用")

        password = data.pop("password", None)
        if password:
            data["hashed_password"] = hash_password(password)

        await self.staff.update(staff, **data)
        if password or data.get("is_active") is False:
            await revoke_all_for_account(self.session, "staff", staff_id)
        await self.session.commit()
        await self.session.refresh(staff)
        return staff

    async def delete(self, staff_id: int, *, actor_id: int | None = None) -> None:
        await self._lock_admin_membership()
        staff = await self.get_or_404(staff_id)
        if actor_id is not None and actor_id == staff_id:
            raise ConflictError("不能删除当前登录的管理员账号")
        if staff.is_active and staff.is_superuser:
            await self._require_another_active_superuser(staff_id)
        await self.staff.delete(staff, soft=True)
        await revoke_all_for_account(self.session, "staff", staff_id)
        await self.session.commit()

    async def delete_many(self, ids: builtins.list[int], *, exclude_id: int | None = None) -> int:
        """批量软删除。保护当前操作者自己，防止超管把后台锁死。"""
        targets = [i for i in ids if i != exclude_id]
        if not targets:
            return 0
        await self._lock_admin_membership()
        targets_admins = (
            (
                await self.session.execute(
                    select(StaffUser.id).where(
                        StaffUser.id.in_(targets),
                        StaffUser.deleted_at.is_(None),
                        StaffUser.is_active.is_(True),
                        StaffUser.is_superuser.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if targets_admins:
            await self._require_another_active_superuser(*targets)
        affected = await self.staff.update_many(targets, deleted_at=datetime.now())
        await revoke_sessions_for_accounts(self.session, "staff", targets)
        await self.session.commit()
        return affected

    async def _lock_admin_membership(self) -> None:
        await self.session.execute(
            select(StaffAdminMutex.id).where(StaffAdminMutex.id == 1).with_for_update()
        )

    async def _active_superuser_count(self, excluded_ids: tuple[int, ...] = ()) -> int:
        stmt = (
            select(func.count())
            .select_from(StaffUser)
            .where(
                StaffUser.deleted_at.is_(None),
                StaffUser.is_active.is_(True),
                StaffUser.is_superuser.is_(True),
            )
        )
        if excluded_ids:
            stmt = stmt.where(StaffUser.id.not_in(excluded_ids))
        return int((await self.session.execute(stmt)).scalar_one())

    async def _require_another_active_superuser(self, *excluded_ids: int) -> None:
        if await self._active_superuser_count(tuple(excluded_ids)) < 1:
            raise ConflictError("至少保留一名启用的超级管理员")
