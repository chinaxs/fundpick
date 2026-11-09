"""模拟买卖的预览、幂等确认和保留痕迹的作废流程。"""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.fund_transaction import FundTransaction
from app.repositories.transaction import TransactionRepository
from app.schemas.common import PageResult
from app.schemas.portfolio import TradeConfirm, TradeInput, TradePreview, TradeRead
from app.services.ledger import replay
from app.services.portfolio_math import calculate
from app.services.trade_timing import receipt_warnings, validate_receipt
from app.trading_calendar import SHANGHAI, local_time


def fingerprint(value: object) -> str:
    """稳定摘要用于检查预览是否过期及请求是否重复。"""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TransactionRepository(session)

    async def preview(self, user_id: int, request: TradeInput) -> TradePreview:
        """只计算、不落库，返回确认后份额、成本及本次已实现收益。"""
        fund = await self.repo.find_fund(request.code)
        if fund is None:
            raise NotFoundError("基金不存在")
        if request.confirmed_on > datetime.now(SHANGHAI).date():
            raise ValidationError("确认日期不能晚于今天")
        validate_receipt(request, fund)
        if fund.inception_date and request.confirmed_on < fund.inception_date:
            raise ValidationError("确认日期早于基金成立日")
        rows = [row for row, _ in await self.repo.rows(user_id) if row.fund_id == fund.id]
        flows = [flow for flow in await self.repo.flows(user_id) if flow.fund_id == fund.id]
        active = [row for row in rows if row.status == "confirmed"]
        if request.submitted_at:
            account_times = [
                row.submitted_at
                for row in active
                if row.platform == (request.platform or "").strip() and row.submitted_at
            ]
            if account_times and local_time(request.submitted_at).replace(tzinfo=None) < max(
                account_times
            ):
                raise ValidationError(
                    "申请时间早于该平台最后一笔有效记录，请按时间顺序录入或先倒序作废后续记录"
                )
        if active and request.confirmed_on < active[-1].confirmed_on:
            raise ValidationError(
                "确认日期早于该基金最后一笔有效交易；请先按倒序作废后续记录再补录"
            )
        await self._validate_legacy(user_id, fund.id, request)
        if request.application_id:
            assert request.submitted_at is not None
            application = await self.repo.application(user_id, request.application_id)
            if application is None or application.status != "pending":
                raise ConflictError("申请记录不存在或已经处理")
            if (
                application.fund_id != fund.id
                or application.kind != request.kind
                or (
                    application.platform
                    and application.platform != (request.platform or "").strip()
                )
                or application.submitted_at != local_time(request.submitted_at).replace(tzinfo=None)
            ):
                raise ValidationError("回执的基金、方向、平台和申请时间需与原申请一致")
        nav = (
            request.nav
            if request.nav_mode == "manual"
            else await self.repo.exact_nav(fund, request.confirmed_on)
        )
        if nav is None or nav <= 0:
            raise ValidationError(
                "该确认日暂无官方净值，请核对日期，或切换为手动填写确认净值；不会使用其他日期替代"
            )
        nav = Decimal(nav).quantize(Decimal("0.000001"))
        platform = (request.platform or "").strip()
        if not platform:
            # 未指定平台时：只有一个平台就直接用；多个平台必须明确，避免拿错账户份额
            platforms = {(row.platform or "") for row in active}
            if len(platforms) > 1:
                raise ValidationError("该基金在多个平台持有，请选择交易平台后再卖出")
        # 全平台重放后投影到该平台：公司行为只影响它归属的平台，
        # 各平台可卖份额之和不会超过全基金持仓。
        before = replay(active, flows, until=request.confirmed_on, platform=platform or None)
        effects = calculate(request, nav, before)
        self._ensure_history_consistent(active, flows, request, platform, nav, effects)
        effect = dict(
            code=fund.code,
            name=fund.name,
            kind=request.kind,
            confirmed_on=request.confirmed_on,
            nav=float(nav),
            nav_source=request.nav_mode,
            note=request.note,
            **{key: float(value) for key, value in effects.items()},
        )
        digest = fingerprint(
            {
                "user": user_id,
                "request": request.model_dump(mode="json"),
                "rows": [(row.id, row.status) for row in rows],
                "effect": effect,
            }
        )
        warnings = receipt_warnings(request, nav) or (
            ["按公开净值和费率自动计算，实际平台结果可校准。"]
            if request.record_source == "estimated"
            else ["旧版折算记录，尚未与平台回执核对。"]
        )
        official = await self.repo.exact_nav(fund, request.confirmed_on)
        if request.record_source == "receipt" and official is not None and official != nav:
            warnings.append(
                f"回执净值 {nav} 与本地同日净值 {official} 不一致，请核对；保存时保留回执值。"
            )
        if request.nav_mode == "manual":
            warnings.append("使用你填写的确认净值，请与成交记录核对。")
        if request.legacy_position_id:
            warnings.append("确认后原记录移出待核对区，仅保留这笔买入计入持仓。")
        return TradePreview(**effect, preview_hash=digest, warnings=warnings)

    @staticmethod
    def _ensure_history_consistent(
        active: list, flows: list, request: TradeInput, platform: str, nav: Decimal, effects: dict
    ) -> None:
        """把本笔交易放进完整历史重放：之后的公司行为不能因此缺份额。

        `before` 只重放到本笔日期，用来算本次成交；但补录一笔过去的卖出，
        可能让之后已经记录的转换/再投无份额可用。这里用"插入后整本账"再验一次，
        买入不会造成短缺，卖出才可能，但两者都走同一条规则。
        """
        candidate = SimpleNamespace(
            id=10**12,  # 排在当日已有流水之后
            kind=request.kind,
            confirmed_on=request.confirmed_on,
            shares=effects["shares"],
            cash_amount=effects["cash_amount"],
            fee=effects["fee"],
            nav=nav,
            platform=platform or None,
            status="confirmed",
            voided_at=None,
            calculation_basis=request.calculation_basis,
            settled_on=request.settled_on,
        )
        state = replay([*active, candidate], flows)
        if state.shortfall > 0 or state.shares < 0:
            raise ValidationError(
                "这笔交易之后还有公司行为依赖更多的份额，按当前顺序录入会把持仓算成负数；"
                "请按时间顺序录入，或先撤销之后的记录"
            )

    async def _validate_legacy(self, user_id: int, fund_id: int, request: TradeInput) -> None:
        if not request.legacy_position_id:
            return
        row = await self.repo.legacy(user_id, request.legacy_position_id)
        if row is None or row.fund_id != fund_id:
            raise NotFoundError("待核对的旧持仓不存在或已迁移")

    async def confirm(self, user_id: int, payload: TradeConfirm) -> TradeRead:
        """锁会员、复核预览、同一请求只成交一次；资金与份额由服务端重算。"""
        await self.repo.lock_member(user_id)
        request_hash = fingerprint(
            {
                "request": payload.request.model_dump(mode="json"),
                "preview_hash": payload.preview_hash,
            }
        )
        existing = await self.repo.by_request(user_id, str(payload.request_key))
        if existing:
            if existing.deleted_at is not None:
                raise ConflictError("这笔记录已删除，重新录入请使用新的请求编号")
            if existing.request_hash != request_hash:
                raise ConflictError("该请求编号已用于另一笔记录，请重新预览")
            return await self._read_one(user_id, existing)
        quote = await self.preview(user_id, payload.request)
        if quote.preview_hash != payload.preview_hash:
            raise ConflictError("持仓或净值已变化，请重新预览后确认")
        fund = await self.repo.find_fund(payload.request.code)
        assert fund is not None
        values = quote.model_dump(exclude={"code", "name", "preview_hash", "warnings"})
        for key in (
            "nav",
            "amount",
            "fee",
            "shares",
            "cash_amount",
            "realized_profit",
            "remaining_shares",
            "remaining_cost",
        ):
            values[key] = Decimal(str(values[key]))
        row = FundTransaction(
            user_id=user_id,
            fund_id=fund.id,
            status="confirmed",
            request_key=str(payload.request_key),
            request_hash=request_hash,
            legacy_position_id=payload.request.legacy_position_id,
            calculation_basis=payload.request.calculation_basis,
            submitted_at=local_time(payload.request.submitted_at).replace(tzinfo=None)
            if payload.request.submitted_at
            else None,
            settled_on=payload.request.settled_on,
            platform=(payload.request.platform or "").strip() or None,
            receipt_ref=payload.request.receipt_ref,
            record_source=payload.request.record_source,
            pricing_rule=payload.request.pricing_rule,
            date_reason=payload.request.date_reason,
            application_id=payload.request.application_id,
            **values,
        )
        self.repo.add(row)
        if payload.request.application_id:
            application = await self.repo.application(user_id, payload.request.application_id)
            assert application is not None
            application.status = "recorded"
            application.processing_message = (
                "已自动入账" if application.automatic_processing else "已按平台结果入账"
            )
            application.next_retry_at = None
            if not application.platform:
                application.platform = (payload.request.platform or "").strip()
        if payload.request.legacy_position_id:
            legacy = await self.repo.legacy(user_id, payload.request.legacy_position_id)
            assert legacy is not None
            legacy.deleted_at = datetime.now()
        await self.session.commit()
        await self.session.refresh(row)
        return await self._read_one(user_id, row)

    async def list(self, user_id: int, page: int, page_size: int) -> PageResult[TradeRead]:
        """流水包含作废记录，按录入顺序倒序分页，不截断组合计算所需历史。"""
        rows = await self.repo.rows(user_id)
        latest = {fund.id: row.id for row, fund in rows if row.status == "confirmed"}
        rows.sort(key=lambda item: item[0].id, reverse=True)
        items = [
            self._serialize(row, fund, latest.get(fund.id) == row.id)
            for row, fund in rows[(page - 1) * page_size : page * page_size]
        ]
        return PageResult(items=items, total=len(rows), page=page, page_size=page_size)

    async def void(self, user_id: int, transaction_id: int, reason: str) -> TradeRead:
        """仅作废同一基金最后一笔有效流水，保留原因并恢复前一持仓状态。"""
        if not reason.strip():
            raise ValidationError("请填写作废原因")
        await self.repo.lock_member(user_id)
        row = await self.repo.owned(user_id, transaction_id)
        if row is None or row.deleted_at is not None:
            raise NotFoundError("交易记录不存在")
        if row.status == "voided":
            return await self._read_one(user_id, row)
        active = [
            r
            for r, _ in await self.repo.rows(user_id)
            if r.fund_id == row.fund_id and r.status == "confirmed"
        ]
        if active[-1].id != row.id:
            raise ConflictError("这笔交易后还有有效记录，请从最后一笔开始倒序作废")
        flows = [flow for flow in await self.repo.flows(user_id) if flow.fund_id == row.fund_id]
        dependent = [flow for flow in flows if flow.effective_on >= row.confirmed_on]
        if dependent:
            raise ConflictError("这笔交易之后还记录了分红/拆分/转换，请先倒序删除这些记录再作废")
        remaining = replay([item for item in active if item.id != row.id], flows)
        if remaining.shortfall > 0 or remaining.shares < 0:
            raise ConflictError("作废后持仓份额为负，请先倒序撤销后续记录")
        row.status, row.voided_at, row.void_reason = "voided", datetime.now(), reason.strip()
        if row.application_id:
            application = await self.repo.application(user_id, row.application_id)
            if application:
                # 已作废流水保留唯一关联，重新入账用新回执，不复用同一申请。
                application.status = "cancelled"
        if row.legacy_position_id:
            legacy = await self.repo.original_legacy(row.legacy_position_id)
            if legacy:
                legacy.deleted_at = None
        await self.session.commit()
        return await self._read_one(user_id, row)

    async def _read_one(self, user_id: int, row: FundTransaction) -> TradeRead:
        rows = await self.repo.rows(user_id)
        fund = next(fund for item, fund in rows if item.id == row.id)
        active = [r for r, _ in rows if r.fund_id == fund.id and r.status == "confirmed"]
        return self._serialize(row, fund, bool(active and active[-1].id == row.id))

    @staticmethod
    def _serialize(row, fund, latest: bool) -> TradeRead:
        fields = {
            key: getattr(row, key)
            for key in (
                "id",
                "kind",
                "status",
                "confirmed_on",
                "nav",
                "nav_source",
                "amount",
                "fee",
                "shares",
                "cash_amount",
                "realized_profit",
                "remaining_shares",
                "remaining_cost",
                "note",
                "legacy_position_id",
                "created_at",
                "voided_at",
                "void_reason",
                "submitted_at",
                "settled_on",
                "platform",
                "receipt_ref",
                "record_source",
                "pricing_rule",
                "date_reason",
                "application_id",
                "calculation_basis",
            )
        }
        if fields["submitted_at"] is not None:
            fields["submitted_at"] = fields["submitted_at"].replace(tzinfo=SHANGHAI)
        return TradeRead(
            code=fund.code, name=fund.name, can_void=latest and row.status == "confirmed", **fields
        )
