"""用户业务逻辑。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.common import PageParams, PageResult
from app.schemas.user import UserCreate, UserQuery, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def get_or_404(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        return user

    async def create(self, payload: UserCreate) -> User:
        if await self.users.exists(username=payload.username):
            raise ConflictError("用户名已存在")
        if payload.email and await self.users.exists(email=payload.email):
            raise ConflictError("邮箱已被占用")

        user = await self.users.create(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            is_staff=payload.is_staff,
            is_superuser=payload.is_superuser,
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def list(self, query: UserQuery, params: PageParams) -> PageResult[User]:
        return await self.users.search(query, params)

    async def update(self, user_id: int, payload: UserUpdate) -> User:
        user = await self.get_or_404(user_id)
        data = payload.model_dump(exclude_unset=True)

        if "email" in data and data["email"] and await self.users.exists(email=data["email"]):
            existing = await self.users.get_by(email=data["email"])
            if existing and existing.id != user_id:
                raise ConflictError("邮箱已被占用")

        password = data.pop("password", None)
        if password:
            data["hashed_password"] = hash_password(password)

        await self.users.update(user, **data)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: int) -> None:
        user = await self.get_or_404(user_id)
        await self.users.delete(user, soft=True)
        await self.session.commit()
