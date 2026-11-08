"""待确认申请：记录真实平台操作，不提前生成份额或收益。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.trade_application import TradeApplication
from app.repositories.transaction import TransactionRepository
from app.schemas.portfolio import ApplicationInput, ApplicationRead, TradeTimingInput
from app.services.trade_timing import expected_day
from app.services.transaction import fingerprint
from app.trading_calendar import SHANGHAI, local_time


class ApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TransactionRepository(session)

    async def create(self, user_id: int, request: ApplicationInput) -> ApplicationRead:
        await self.repo.lock_member(user_id)
        digest = fingerprint(request.model_dump(mode="json", exclude={"request_key"}))
        existing = await self.repo.application_request(user_id, str(request.request_key))
        fund = await self.repo.find_fund(request.code)
        if fund is None:
            raise NotFoundError("基金不存在")
        if existing:
            if existing.deleted_at is not None:
                raise ConflictError("这笔记录已删除，重新录入请使用新的请求编号")
            if existing.request_hash != digest:
                raise ConflictError("申请编号已用于另一条记录")
            data = self.read(existing, fund)
            await self.session.commit()  # 结束等待写锁前的快照，释放会员锁。
            return data
        day = expected_day(fund, TradeTimingInput(**request.model_dump()))
        row = TradeApplication(
            user_id=user_id,
            fund_id=fund.id,
            kind=request.kind,
            submitted_at=local_time(request.submitted_at).replace(tzinfo=None),
            expected_nav_on=day,
            platform=(request.platform or "").strip(),
            pricing_rule="cn_open" if day else "platform",
            amount=request.amount,
            shares=request.shares,
            note=request.note,
            status="pending",
            request_key=str(request.request_key),
            request_hash=digest,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self.read(row, fund)

    async def list(self, user_id: int) -> list[ApplicationRead]:
        return [self.read(row, fund) for row, fund in await self.repo.applications(user_id)]

    async def cancel(self, user_id: int, application_id: int):
        await self.repo.lock_member(user_id)
        row = await self.repo.application(user_id, application_id)
        if row is None or row.deleted_at is not None:
            raise NotFoundError("申请记录不存在")
        if row.status == "recorded":
            raise ConflictError("已入账记录请到交易流水作废")
        row.status = "cancelled"
        await self.session.commit()

    @staticmethod
    def read(row, fund):
        return ApplicationRead(
            requires_review=(
                not row.automatic_processing
                or row.expected_nav_on is None
                or any(
                    word in (row.processing_message or "")
                    for word in ("不足", "不明确", "多个平台", "早于", "超过", "待核对")
                )
            ),
            automatic_processing=row.automatic_processing,
            processing_message=row.processing_message,
            id=row.id,
            code=fund.code,
            name=fund.name,
            kind=row.kind,
            submitted_at=row.submitted_at.replace(tzinfo=SHANGHAI),
            platform=row.platform,
            pricing_rule=row.pricing_rule,
            expected_nav_on=row.expected_nav_on,
            amount=str(row.amount) if row.amount is not None else None,
            shares=str(row.shares) if row.shares is not None else None,
            status=row.status,
            note=row.note,
        )
