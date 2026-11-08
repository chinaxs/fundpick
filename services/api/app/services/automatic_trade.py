"""两项输入自动查净值和费用；缺数据保持待处理，计算结果保留估算来源。"""

import re
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.repositories.transaction import TransactionRepository
from app.schemas.portfolio import AutoTradeInput, AutoTradeRead, TradeConfirm, TradeInput
from app.services.automatic_lookup import lookup_nav, lookup_rules
from app.services.ledger import replay
from app.services.trade_application import ApplicationService
from app.services.trade_fee_math import fee_for, redemption_fee
from app.services.transaction import TransactionService
from app.trading_calendar import SHANGHAI, advance_trading_days


class AutomaticTradeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TransactionRepository(session)

    async def save(self, user_id: int, request: AutoTradeInput) -> AutoTradeRead:
        item = await ApplicationService(self.session).create(user_id, request)
        row = await self.repo.application(user_id, item.id)
        if row and row.status == "pending":
            row.automatic_processing = True
            await self.session.commit()
        return await self.resolve(user_id, item.id)

    async def resolve(self, user_id: int, application_id: int) -> AutoTradeRead:
        await self.session.rollback()  # 清除读快照；此前创建申请已独立提交。
        application = await self.repo.application(user_id, application_id)
        if application is None or application.deleted_at is not None:
            raise ValidationError("记录不存在")
        existing = await self.repo.by_application(user_id, application_id)
        if existing and existing.status == "voided":
            raise ConflictError("该自动记录已作废，重新录入请使用新记录")
        if existing:
            trade = await TransactionService(self.session)._read_one(user_id, existing)
            return AutoTradeRead(status="recorded", transaction=trade, message="已自动计算并记录")
        if application.status != "pending":
            raise ConflictError("记录已处理")
        fund = await self.repo.fund_by_id(application.fund_id)
        if fund is None:
            raise ValidationError("基金不存在")
        if not application.expected_nav_on:
            return await self.pending(application, fund, "特殊交易日期待平台结果确认")
        day, fund_id, code = application.expected_nav_on, fund.id, fund.code
        nav = await lookup_nav(self.repo, fund, day)
        if nav is None:
            return await self.pending(application, fund, f"等待 {day} 的官方净值，公布后自动计算")
        rules, source, fetched = await lookup_rules(fund_id, code)
        # 外部补查使用独立会话提交；重开快照后读取新净值与最新持仓。
        await self.session.rollback()
        application = await self.repo.application(user_id, application_id)
        fund = await self.repo.fund_by_id(fund_id)
        assert application is not None and fund is not None
        existing = await self.repo.by_application(user_id, application_id)
        if existing:
            trade = await TransactionService(self.session)._read_one(user_id, existing)
            return AutoTradeRead(status="recorded", transaction=trade, message="已自动计算并记录")
        if application.status != "pending":
            raise ConflictError("记录已处理")
        confirmation_rules = [
            rule["standard"]
            for rule in rules
            if rule["kind"] == "confirmation"
            and rule["condition"] == ("买入确认日" if application.kind == "buy" else "卖出确认日")
        ]
        match = (
            re.fullmatch(r"T\+(\d{1,2})", confirmation_rules[0])
            if len(confirmation_rules) == 1
            else None
        )
        if match is None:
            return await self.pending(
                application, fund, "交易费率或确认周期暂未取得，等待查询，不提前入账"
            )
        try:
            expected_confirmation = advance_trading_days(day, int(match[1]))
        except ValidationError:
            return await self.pending(application, fund, "确认日超出已核对日历范围，需要核对异常")
        if datetime.now(SHANGHAI).date() < expected_confirmation:
            return await self.pending(
                application,
                fund,
                f"按 {day} 净值，公开规则 {confirmation_rules[0]}，"
                f"预计 {expected_confirmation} 自动入账",
            )
        rows = [
            row
            for row, _ in await self.repo.rows(user_id)
            if row.fund_id == fund_id and row.status == "confirmed"
        ]
        flows = [flow for flow in await self.repo.flows(user_id) if flow.fund_id == fund_id]
        platform = application.platform
        if not platform:
            # 转换/再投也可能产生持仓，不能只从买卖流水判断平台。
            # 只看本笔定价日实际有份额的平台，已清仓/未来平台不影响这次判断。
            state = replay(rows, flows, until=day)
            accounts = {key for key, shares in state.platform_shares.items() if shares > 0}
            if len(accounts) == 1:
                platform = accounts.pop()
            elif application.kind == "sell" and len(accounts) > 1:
                return await self.pending(
                    application, fund, "该基金在多个平台持有，请在补充结果中选择交易平台"
                )
        basis = {
            "expected_confirm_on": str(expected_confirmation),
            "confirmation_rule": confirmation_rules[0],
            "source_url": source,
            "fetched_at": str(fetched),
            "nav_date": str(day),
            "nav": str(nav),
            "platform": platform,
            "note": "公开费率与当前持仓自动计算，平台折扣/确认精度可能不同；实际结果可校准",
        }
        if application.kind == "buy":
            result = fee_for(rules, "buy", application.amount, application.amount, platform)
            if result is None:
                return await self.pending(
                    application, fund, "申购费率暂未取得或条件不明确，稍后自动重试"
                )
            fee, detail = result
            basis["fee_rules"] = [detail]
        else:
            result = redemption_fee(rules, rows, application.shares, day, nav, platform, flows)
            if result is None:
                return await self.pending(
                    application, fund, "赎回费率或持有批次信息不足，费用待核对"
                )
            fee, details = result
            basis["fee_rules"] = details
        request = TradeInput(
            code=code,
            kind=application.kind,
            confirmed_on=day,
            record_source="estimated",
            submitted_at=application.submitted_at.replace(tzinfo=SHANGHAI),
            platform=platform or None,
            pricing_rule="cn_open",
            nav_mode="official",
            amount=application.amount,
            shares=application.shares,
            fee=fee,
            application_id=application.id,
            calculation_basis=basis,
            note=application.note,
        )
        try:
            service = TransactionService(self.session)
            quote = await service.preview(user_id, request)
            trade = await service.confirm(
                user_id,
                TradeConfirm(
                    request=request,
                    preview_hash=quote.preview_hash,
                    request_key=uuid5(NAMESPACE_URL, f"fundpick:auto:{user_id}:{application_id}"),
                ),
            )
        except (ConflictError, ValidationError) as exc:
            await self.session.rollback()
            existing = await self.repo.by_application(user_id, application_id)
            if existing and existing.status == "confirmed":
                trade = await TransactionService(self.session)._read_one(user_id, existing)
                return AutoTradeRead(
                    status="recorded", transaction=trade, message="已自动计算并记录"
                )
            application = await self.repo.application(user_id, application_id)
            fund = await self.repo.fund_by_id(fund_id)
            return await self.pending(application, fund, str(exc))
        return AutoTradeRead(
            status="recorded", transaction=trade, message="已自动计算净值、费用和份额"
        )

    async def pending(self, application, fund, message):
        application.processing_message = message[:500]
        await self.session.commit()
        return AutoTradeRead(
            status="pending",
            application=ApplicationService.read(application, fund),
            message=message,
        )

    async def refresh_pending(self, user_id: int, limit=5):
        ids = [
            row.id for row, _ in await self.repo.applications(user_id) if row.automatic_processing
        ][:limit]
        for application_id in ids:
            await self.resolve(user_id, application_id)


async def reconcile_after_sync(limit: int = 50):
    """既有采集任务更新净值后补齐待处理记录，不新增隐式调度器。"""
    from app.core.logging import get_logger
    from app.db.session import async_session_factory

    logger = get_logger(__name__)
    async with async_session_factory() as session:
        members = await TransactionRepository(session).automatic_pending_members(limit)
    for user_id in members:
        async with async_session_factory() as session:
            try:
                await AutomaticTradeService(session).refresh_pending(user_id)
            except Exception as exc:
                await session.rollback()
                logger.warning("自动记账补齐失败 user_id=%s error=%s", user_id, type(exc).__name__)
