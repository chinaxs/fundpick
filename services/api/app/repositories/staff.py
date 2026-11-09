"""后台员工账号仓储。"""

from __future__ import annotations

from sqlalchemy import or_, select

from app.models.staff import StaffUser
from app.repositories.base import BaseRepository
from app.schemas.common import PageParams, PageResult
from app.schemas.staff import StaffQuery


class StaffUserRepository(BaseRepository[StaffUser]):
    model = StaffUser

    async def get_by_username_or_email(self, identifier: str) -> StaffUser | None:
        stmt = self._base_stmt().where(
            or_(StaffUser.username == identifier, StaffUser.email == identifier)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def exists(self, *, username: str | None = None, email: str | None = None) -> bool:
        stmt = select(StaffUser.id)
        conditions = []
        if username:
            conditions.append(StaffUser.username == username)
        if email:
            conditions.append(StaffUser.email == email)
        if not conditions:
            return False
        stmt = stmt.where(or_(*conditions))
        return (await self.session.execute(stmt.limit(1))).scalar_one_or_none() is not None

    async def search(self, query: StaffQuery, params: PageParams) -> PageResult[StaffUser]:
        stmt = self._base_stmt()
        if query.keyword:
            like = f"%{query.keyword}%"
            stmt = stmt.where(or_(StaffUser.username.like(like), StaffUser.email.like(like)))
        if query.is_active is not None:
            stmt = stmt.where(StaffUser.is_active == query.is_active)
        stmt = stmt.order_by(StaffUser.id)
        return await self.paginate(stmt, params)
