"""审计日志查询。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.schemas.admin import AuditQuery


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _filters(stmt, query: AuditQuery):
        if query.username:
            stmt = stmt.where(AuditLog.username.like(f"%{query.username}%"))
        if query.resource:
            stmt = stmt.where(AuditLog.resource == query.resource)
        if query.action:
            stmt = stmt.where(AuditLog.action == query.action)
        if query.status_code is not None:
            stmt = stmt.where(AuditLog.status_code == query.status_code)
        if query.start:
            stmt = stmt.where(AuditLog.created_at >= query.start)
        if query.end:
            stmt = stmt.where(AuditLog.created_at <= query.end)
        return stmt

    async def search(
        self, query: AuditQuery, page: int, page_size: int
    ) -> tuple[list[AuditLog], int]:
        base = self._filters(select(AuditLog), query)
        total = int(
            (
                await self.session.execute(
                    self._filters(select(func.count()).select_from(AuditLog), query)
                )
            ).scalar_one()
        )
        stmt = (
            base.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows, total
