"""后台员工账号业务逻辑（staff_users 表）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.staff import StaffUser
from app.repositories.staff import StaffUserRepository
from app.schemas.common import PageParams, PageResult
from app.schemas.staff import StaffCreate, StaffQuery, StaffUpdate


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

    async def update(self, staff_id: int, payload: StaffUpdate) -> StaffUser:
        staff = await self.get_or_404(staff_id)
        data = payload.model_dump(exclude_unset=True)

        if "email" in data and data["email"] and await self.staff.exists(email=data["email"]):
            existing = await self.staff.get_by(email=data["email"])
            if existing and existing.id != staff_id:
                raise ConflictError("邮箱已被占用")

        password = data.pop("password", None)
        if password:
            data["hashed_password"] = hash_password(password)

        await self.staff.update(staff, **data)
        await self.session.commit()
        await self.session.refresh(staff)
        return staff

    async def delete(self, staff_id: int) -> None:
        staff = await self.get_or_404(staff_id)
        await self.staff.delete(staff, soft=True)
        await self.session.commit()

    async def delete_many(self, ids: list[int], *, exclude_id: int | None = None) -> int:
        """批量软删除。保护当前操作者自己，防止超管把后台锁死。"""
        targets = [i for i in ids if i != exclude_id]
        if not targets:
            return 0
        affected = await self.staff.update_many(targets, deleted_at=datetime.now())
        await self.session.commit()
        return affected
