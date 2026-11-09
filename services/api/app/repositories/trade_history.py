"""会员统一交易记录：数据库筛选、UNION分页，不截取全量流水后内存分页。"""

from datetime import datetime, time, timedelta

from sqlalchemy import exists, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.models.fund_transaction import FundTransaction
from app.models.trade_application import TradeApplication
from app.schemas.portfolio import TradeHistoryQuery


class TradeHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _query(self, user_id: int, query: TradeHistoryQuery):
        def branch(model, record_type, statuses):
            occurred = func.coalesce(model.submitted_at, model.created_at)
            statement = (
                select(
                    literal(record_type).label("record_type"),
                    model.id.label("id"),
                    occurred.label("occurred_at"),
                )
                .join(Fund, Fund.id == model.fund_id)
                .where(
                    model.user_id == user_id, model.deleted_at.is_(None), model.status.in_(statuses)
                )
            )
            if record_type == "application":
                # 自动成交及其作废/删除仍代表同一笔记录，不能再冒出一条撤销申请。
                statement = statement.where(
                    ~exists().where(
                        FundTransaction.application_id == TradeApplication.id,
                        FundTransaction.user_id == user_id,
                    )
                )
            if query.keyword and query.keyword.strip():
                keyword = query.keyword.strip()
                statement = statement.where(
                    or_(
                        Fund.name.contains(keyword, autoescape=True),
                        Fund.code.contains(keyword, autoescape=True),
                    )
                )
            if query.kind:
                statement = statement.where(model.kind == query.kind)
            if query.status:
                statement = statement.where(model.status == query.status)
            if query.start:
                statement = statement.where(occurred >= datetime.combine(query.start, time.min))
            if query.end:
                statement = statement.where(
                    occurred < datetime.combine(query.end + timedelta(days=1), time.min)
                )
            return statement

        return union_all(
            branch(FundTransaction, "transaction", ["confirmed", "voided"]),
            branch(TradeApplication, "application", ["pending", "cancelled"]),
        ).subquery()

    async def page(self, user_id: int, query: TradeHistoryQuery):
        records = self._query(user_id, query)
        total = (await self.session.execute(select(func.count()).select_from(records))).scalar_one()
        rows = (
            (
                await self.session.execute(
                    select(records)
                    .order_by(
                        records.c.occurred_at.desc(),
                        records.c.id.desc(),
                        records.c.record_type.desc(),
                    )
                    .offset((query.page - 1) * query.page_size)
                    .limit(query.page_size)
                )
            )
            .mappings()
            .all()
        )
        return [(row["record_type"], row["id"]) for row in rows], int(total)

    async def transactions(self, user_id: int, ids: list[int]):
        if not ids:
            return []
        result = await self.session.execute(
            select(FundTransaction, Fund)
            .join(Fund, Fund.id == FundTransaction.fund_id)
            .where(
                FundTransaction.user_id == user_id,
                FundTransaction.id.in_(ids),
                FundTransaction.deleted_at.is_(None),
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def applications(self, user_id: int, ids: list[int]):
        if not ids:
            return []
        result = await self.session.execute(
            select(TradeApplication, Fund)
            .join(Fund, Fund.id == TradeApplication.fund_id)
            .where(
                TradeApplication.user_id == user_id,
                TradeApplication.id.in_(ids),
                TradeApplication.deleted_at.is_(None),
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def latest_ids(self, user_id: int, fund_ids: list[int]):
        if not fund_ids:
            return set()
        result = await self.session.execute(
            select(func.max(FundTransaction.id))
            .where(
                FundTransaction.user_id == user_id,
                FundTransaction.fund_id.in_(fund_ids),
                FundTransaction.status == "confirmed",
                FundTransaction.deleted_at.is_(None),
            )
            .group_by(FundTransaction.fund_id)
        )
        return set(result.scalars())
