"""用户仓储。"""

from __future__ import annotations

from sqlalchemy import or_, select

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.common import PageParams, PageResult
from app.schemas.user import UserQuery


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        stmt = self._base_stmt().where(or_(User.username == identifier, User.email == identifier))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def exists(self, *, username: str | None = None, email: str | None = None) -> bool:
        stmt = select(User.id)
        conditions = []
        if username:
            conditions.append(User.username == username)
        if email:
            conditions.append(User.email == email)
        if not conditions:
            return False
        stmt = stmt.where(or_(*conditions))
        return (await self.session.execute(stmt.limit(1))).scalar_one_or_none() is not None

    async def search(self, query: UserQuery, params: PageParams) -> PageResult[User]:
        stmt = self._base_stmt()
        if query.keyword:
            like = f"%{query.keyword}%"
            stmt = stmt.where(or_(User.username.like(like), User.email.like(like)))
        if query.is_active is not None:
            stmt = stmt.where(User.is_active == query.is_active)
        stmt = stmt.order_by(User.id.desc())
        return await self.paginate(stmt, params)
