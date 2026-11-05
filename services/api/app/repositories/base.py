"""通用仓储层：把 CRUD 细节收在这里，service 只管业务。"""

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.schemas.common import PageParams, PageResult

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """基础仓储，子类指定 model 即可获得通用能力。"""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------- 查询
    def _base_stmt(self) -> Select[tuple[ModelT]]:
        stmt = select(self.model)
        if hasattr(self.model, "deleted_at"):  # 软删除模型默认过滤
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    async def get(self, pk: int) -> ModelT | None:
        stmt = self._base_stmt().where(self.model.id == pk)  # type: ignore[attr-defined]
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many(self, ids: list[int]) -> list[ModelT]:
        """按 ID 批量取（软删除自动过滤），返回实际存在的行。"""
        if not ids:
            return []
        stmt = self._base_stmt().where(self.model.id.in_(ids))  # type: ignore[attr-defined]
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_many(self, ids: list[int], **values: Any) -> int:
        """按 ID 批量更新，返回受影响行数（软删除行不参与）。"""
        if not ids or not values:
            return 0
        stmt = (
            self.model.__table__.update()
            .where(self.model.id.in_(ids))  # type: ignore[attr-defined]
            .values(**values)
        )
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)

    async def get_by(self, **filters: Any) -> ModelT | None:
        stmt = self._base_stmt()
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = self._base_stmt().order_by(self.model.id.desc()).limit(limit).offset(offset)  # type: ignore[attr-defined]
        return list((await self.session.execute(stmt)).scalars().all())

    async def paginate(self, stmt: Select[tuple[ModelT]], params: PageParams) -> PageResult[Any]:
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            (await self.session.execute(stmt.limit(params.page_size).offset(params.offset)))
            .scalars()
            .all()
        )
        return PageResult(
            items=list(rows), total=total, page=params.page, page_size=params.page_size
        )

    # ---------------------------------------------------------- 写入
    async def create(self, **values: Any) -> ModelT:
        obj = self.model(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelT, **values: Any) -> ModelT:
        for field, value in values.items():
            if value is not None and hasattr(obj, field):
                setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT, *, soft: bool = True) -> None:
        """默认软删除；硬删除需显式 soft=False。"""
        if soft and hasattr(obj, "deleted_at"):
            from datetime import datetime

            obj.deleted_at = datetime.now()  # type: ignore[attr-defined]
            await self.session.flush()
        else:
            await self.session.delete(obj)
            await self.session.flush()
