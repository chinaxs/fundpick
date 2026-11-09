"""统一展示申请与成交；删除仅清理已失效记录，不改变持仓。"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.trade_history import TradeHistoryRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.common import PageResult
from app.schemas.portfolio import TradeHistoryItem, TradeHistoryQuery
from app.services.trade_application import ApplicationService
from app.services.transaction import TransactionService
from app.trading_calendar import SHANGHAI


class TradeHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.history = TradeHistoryRepository(session)
        self.transactions = TransactionRepository(session)

    async def list(self, user_id: int, query: TradeHistoryQuery) -> PageResult[TradeHistoryItem]:
        keys, total = await self.history.page(user_id, query)
        rows = await self.history.transactions(
            user_id, [id for kind, id in keys if kind == "transaction"]
        )
        applications = await self.history.applications(
            user_id, [id for kind, id in keys if kind == "application"]
        )
        latest = await self.history.latest_ids(user_id, list({fund.id for _, fund in rows}))
        items = {}
        for row, fund in rows:
            trade = TransactionService._serialize(row, fund, row.id in latest)
            items[("transaction", row.id)] = TradeHistoryItem(
                record_type="transaction", can_delete=row.status == "voided", **trade.model_dump()
            )
        for row, fund in applications:
            application = ApplicationService.read(row, fund)
            items[("application", row.id)] = TradeHistoryItem(
                record_type="application",
                id=row.id,
                code=fund.code,
                name=fund.name,
                kind=row.kind,
                status=row.status,
                submitted_at=row.submitted_at.replace(tzinfo=SHANGHAI),
                created_at=row.created_at,
                expected_nav_on=row.expected_nav_on,
                platform=row.platform or None,
                amount=float(row.amount) if row.amount is not None else None,
                shares=float(row.shares) if row.shares is not None else None,
                note=row.note,
                can_cancel=row.status == "pending",
                can_delete=row.status == "cancelled",
                requires_review=application.requires_review,
                processing_message=row.processing_message,
            )
        return PageResult(
            items=[items[key] for key in keys if key in items],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def delete(self, user_id: int, record_type: str, record_id: int) -> None:
        await self.transactions.lock_member(user_id)
        row = (
            await self.transactions.owned(user_id, record_id)
            if record_type == "transaction"
            else await self.transactions.application(user_id, record_id)
        )
        if row is None:
            raise NotFoundError("记录不存在")
        if row.deleted_at is not None:
            return
        expected = "voided" if record_type == "transaction" else "cancelled"
        if row.status != expected:
            raise ConflictError("仅已作废或已撤销的记录可以删除")
        row.deleted_at = datetime.now()
        await self.session.commit()
