"""持仓工具：历史导入、公司行为流水、导出与收益核对。

三条硬约束：

1. **导入只用于"从零开始"**：某只基金已有交易记录时拒绝导入，
   否则同一段历史会被记两遍，份额直接翻倍；
2. **公司行为不改写已确认份额**：分红/拆分/转换单独成表，核对时叠加展示，
   保持"回执份额"这一唯一可信来源；
3. **导出就是账本的原始视图**：不做二次计算，方便用户拿去和平台对账。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.fund import Fund
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.user import User
from app.schemas.portfolio_tools import (
    FLOW_KIND_LABELS,
    FlowCreate,
    FlowRead,
    ImportRequest,
    ImportResult,
    ImportRowError,
    ReconciliationFund,
    ReconciliationResult,
)
from app.services.ledger import LedgerState, exit_cost, replay

SHARE_STEP = Decimal("0.0001")


@dataclass
class _LedgerEntry:
    """某只基金的台账快照：最新剩余份额与成本。"""

    code: str
    name: str
    shares: Decimal
    cost: Decimal


def _money(value: Decimal | None) -> float:
    return float(value or 0)


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class PortfolioToolsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------- 基金字典
    async def _fund_map(self, codes: list[str]) -> dict[str, Fund]:
        if not codes:
            return {}
        rows = (
            await self.session.execute(
                select(Fund).where(Fund.code.in_(codes), Fund.deleted_at.is_(None))
            )
        ).scalars()
        return {fund.code: fund for fund in rows}

    # ---------------------------------------------------------- 导入
    async def import_positions(self, user_id: int, payload: ImportRequest) -> ImportResult:
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())
        funds = await self._fund_map([row.code for row in payload.rows])
        errors: list[ImportRowError] = []

        # 已存在交易记录的基金不允许导入：避免历史被记两遍
        existing = set(
            (
                await self.session.execute(
                    select(FundTransaction.fund_id)
                    .where(
                        FundTransaction.user_id == user_id,
                        FundTransaction.deleted_at.is_(None),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

        prepared: list[tuple[FundTransaction, dict[str, str]]] = []
        balances: dict[tuple[int, str], tuple[Decimal, Decimal]] = {}
        for index, row in sorted(
            enumerate(payload.rows, start=1), key=lambda item: (item[1].confirmed_on, item[0])
        ):
            fund = funds.get(row.code)
            if fund is None:
                errors.append(ImportRowError(index=index, code=row.code, reason="基金代码不存在"))
                continue
            if fund.id in existing:
                errors.append(
                    ImportRowError(
                        index=index,
                        code=row.code,
                        reason="该基金已有交易记录，请用「补充录入」或先在交易记录中作废后再导入",
                    )
                )
                continue
            try:
                shares, amount, nav = self._resolve_numbers(row.shares, row.amount, row.nav)
            except ValidationError as exc:
                errors.append(ImportRowError(index=index, code=row.code, reason=exc.message))
                continue
            if row.confirmed_on < (fund.inception_date or row.confirmed_on):
                errors.append(
                    ImportRowError(index=index, code=row.code, reason="确认日期早于基金成立日")
                )
                continue

            account = (fund.id, (row.platform or "").strip())
            bought, cost = balances.get(account, (Decimal(0), Decimal(0)))
            bought += shares
            cost += amount
            balances[account] = (bought, cost)
            transaction = FundTransaction(
                user_id=user_id,
                fund_id=fund.id,
                kind="buy",
                status="confirmed",
                confirmed_on=row.confirmed_on,
                submitted_at=None,
                platform=(row.platform or "").strip() or None,
                calculation_basis={"import": True},
                record_source="import",
                pricing_rule="imported",
                nav=nav.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                nav_source="import",
                amount=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                fee=Decimal("0.00"),
                shares=shares.quantize(SHARE_STEP, rounding=ROUND_HALF_UP),
                cash_amount=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                realized_profit=Decimal("0.00"),
                remaining_shares=bought.quantize(SHARE_STEP, rounding=ROUND_HALF_UP),
                remaining_cost=cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                request_key=str(uuid.uuid4()),
                request_hash=_fingerprint(
                    {
                        "code": row.code,
                        "date": row.confirmed_on,
                        "shares": str(shares),
                        "amount": str(amount),
                    }
                ),
                note=row.note or "历史持仓导入",
            )
            prepared.append(
                (
                    transaction,
                    {
                        "code": row.code,
                        "name": fund.name,
                        "confirmed_on": row.confirmed_on.isoformat(),
                        "shares": str(transaction.shares),
                        "amount": str(transaction.amount),
                    },
                )
            )

        if payload.dry_run:
            return ImportResult(
                created=0,
                dry_run=True,
                errors=errors,
                imported=[summary for _, summary in prepared],
            )

        for transaction, _ in prepared:
            self.session.add(transaction)
        if prepared:
            await self.session.commit()
        return ImportResult(
            created=len(prepared),
            errors=errors,
            imported=[summary for _, summary in prepared],
        )

    @staticmethod
    def _resolve_numbers(
        shares: Decimal | None, amount: Decimal | None, nav: Decimal | None
    ) -> tuple[Decimal, Decimal, Decimal]:
        if shares is not None and nav is not None and shares > 0 and nav > 0:
            return shares, amount if amount is not None else shares * nav, nav
        if amount is not None and nav is not None and nav > 0:
            return (amount / nav).quantize(SHARE_STEP), amount, nav
        if amount is not None and shares is not None and shares > 0:
            return shares, amount, (amount / shares).quantize(Decimal("0.000001"))
        raise ValidationError("份额、金额、净值至少填写两项")

    # ---------------------------------------------------------- 公司行为
    async def list_flows(self, user_id: int, limit: int = 100) -> list[FlowRead]:
        rows = (
            await self.session.execute(
                select(FundPortfolioFlow, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundPortfolioFlow.fund_id)
                .where(
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.deleted_at.is_(None),
                )
                .order_by(FundPortfolioFlow.effective_on.desc(), FundPortfolioFlow.id.desc())
                .limit(limit)
            )
        ).all()
        target_ids = {flow.target_fund_id for flow, _, _ in rows if flow.target_fund_id}
        target_codes: dict[int, str] = {}
        if target_ids:
            pairs = (
                await self.session.execute(
                    select(Fund.id, Fund.code).where(Fund.id.in_(target_ids))
                )
            ).all()
            target_codes = dict(pairs)
        return [
            FlowRead(
                id=flow.id,
                code=code,
                fund_name=name,
                kind=flow.kind,
                kind_label=FLOW_KIND_LABELS.get(flow.kind, flow.kind),
                effective_on=flow.effective_on,
                cash_amount=float(flow.cash_amount) if flow.cash_amount is not None else None,
                net_amount=float(flow.net_amount) if flow.net_amount is not None else None,
                shares_delta=float(flow.shares_delta) if flow.shares_delta is not None else None,
                nav=float(flow.nav) if flow.nav is not None else None,
                ratio=float(flow.ratio) if flow.ratio is not None else None,
                target_code=target_codes.get(flow.target_fund_id or 0),
                platform=flow.platform,
                note=flow.note,
                created_at=flow.created_at,
            )
            for flow, code, name in rows
        ]

    # ---------------------------------------------------------- 串行化与平台归属
    async def _lock(self, user_id: int) -> None:
        """与买卖、导入共用同一把会员锁：读余额到写入必须串行。"""
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())

    async def _state(
        self,
        user_id: int,
        fund_id: int,
        *,
        until: date | None = None,
        platform: str | None = None,
        exclude_flow_ids: set[int] | None = None,
    ) -> LedgerState:
        """当前读重放：加锁后的查询必须读到已提交的最新流水。"""
        skip = exclude_flow_ids or set()
        tx_rows = (
            (
                await self.session.execute(
                    select(FundTransaction)
                    .where(
                        FundTransaction.user_id == user_id,
                        FundTransaction.fund_id == fund_id,
                        FundTransaction.deleted_at.is_(None),
                    )
                    .order_by(FundTransaction.confirmed_on, FundTransaction.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        flow_rows = (
            (
                await self.session.execute(
                    select(FundPortfolioFlow)
                    .where(
                        FundPortfolioFlow.user_id == user_id,
                        FundPortfolioFlow.fund_id == fund_id,
                        FundPortfolioFlow.deleted_at.is_(None),
                    )
                    .order_by(FundPortfolioFlow.effective_on, FundPortfolioFlow.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        return replay(
            list(tx_rows),
            [flow for flow in flow_rows if flow.id not in skip],
            until=until,
            platform=platform,
        )

    async def _resolve_platform(
        self, user_id: int, fund_id: int, day: date, requested: str | None
    ) -> str:
        """确定公司行为归属的平台。

        用户指定优先；只有一个持仓平台时自动补齐；**多平台且未指定时拒绝**。
        再投、分红到底发生在 A 还是 B，是我们查不到的外部事实，
        按"份额最大"猜一个会把平台余额、FIFO 批次和赎回费都算错；
        可复现不等于真实，所以这里要求用户自己选。
        """
        if requested and requested.strip():
            return requested.strip()
        state = await self._state(user_id, fund_id, until=day)
        held = state.platform_shares
        if not held:
            return ""
        if len(held) == 1:
            return next(iter(held))
        names = "、".join(sorted(held))
        raise ValidationError(f"该基金在多个平台持有（{names}），请选择这笔记录归属的平台后再保存")

    async def _consumed_cost(
        self,
        user_id: int,
        fund_id: int,
        day: date,
        shares: Decimal,
        platform: str | None = None,
    ) -> tuple[Decimal, Decimal]:
        """按移动平均算出该平台转出份额对应的成本与不足份额（与卖出同口径）。"""
        state = await self._state(user_id, fund_id, until=day, platform=platform or None)
        return exit_cost(state, shares)

    # ---------------------------------------------------------- 公司行为
    @staticmethod
    def _payload_hash(payload: FlowCreate) -> str:
        """幂等键对应的内容摘要：同一个键换了内容必须冲突，不能沿用旧记录。"""
        fields = (
            "code",
            "kind",
            "effective_on",
            "cash_amount",
            "shares_delta",
            "nav",
            "ratio",
            "target_code",
            "target_shares",
            "target_nav",
            "target_cash_amount",
            "platform",
        )
        data = {name: str(getattr(payload, name)) for name in fields}
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    async def _by_request_key(self, user_id: int, key: str) -> FundPortfolioFlow | None:
        """按幂等键查记录，**包含已删除的墓碑**。"""
        return (
            await self.session.execute(
                select(FundPortfolioFlow)
                .where(
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.request_key == key,
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def add_flow(self, user_id: int, payload: FlowCreate) -> FlowRead:
        await self._lock(user_id)
        digest = self._payload_hash(payload)
        if payload.request_key:
            existing = await self._by_request_key(user_id, payload.request_key)
            if existing is not None:
                if existing.deleted_at is not None:
                    # 墓碑：旧请求重试不能把已删除的分红/再投重新入账
                    raise ConflictError("该请求号的记录已被删除，请使用新的请求号重新录入")
                if (existing.request_hash or "") != digest:
                    raise ConflictError(
                        "该请求号已用于另一笔内容不同的记录，请重新提交并生成新的请求号"
                    )
                return await self._to_read(existing)

        funds = await self._fund_map(
            [payload.code] + ([payload.target_code] if payload.target_code else [])
        )
        fund = funds.get(payload.code)
        if fund is None:
            raise NotFoundError("基金不存在")
        target = funds.get(payload.target_code) if payload.target_code else None
        if payload.target_code and target is None:
            raise NotFoundError("对手基金不存在")
        if target is not None and target.id == fund.id:
            raise ValidationError("转换的对手基金不能是同一只")

        affected: set[int] = {fund.id}
        if payload.kind in {"convert_in", "convert_out"}:
            primary, flows = await self._create_transfer(user_id, fund, target, payload)
            affected |= {row.fund_id for row in flows}
        elif payload.kind == "split":
            # 拆分是基金级事件：按比例作用于所有平台，不需要归属平台
            primary = FundPortfolioFlow(
                user_id=user_id,
                fund_id=fund.id,
                kind="split",
                effective_on=payload.effective_on,
                ratio=payload.ratio,
                shares_delta=payload.shares_delta,
                note=payload.note,
            )
            flows = [primary]
        else:
            platform = await self._resolve_platform(
                user_id, fund.id, payload.effective_on, payload.platform
            )
            primary = FundPortfolioFlow(
                user_id=user_id,
                fund_id=fund.id,
                kind=payload.kind,
                effective_on=payload.effective_on,
                cash_amount=payload.cash_amount,
                shares_delta=payload.shares_delta,
                nav=payload.nav,
                platform=platform,
                note=payload.note,
            )
            flows = [primary]

        if payload.request_key:
            primary.request_key = payload.request_key
            primary.request_hash = digest
        for row in flows:
            self.session.add(row)
        await self.session.flush()

        # 任何影响历史份额的事件都要验证**整本账**：补录一笔过去的转换
        # 不能把之后已经成交的卖出变成负份额。
        for fund_id in sorted(affected):
            state = await self._state(user_id, fund_id)
            if state.shortfall > 0 or state.shares < 0 or state.cost < 0:
                missing = state.shortfall or -state.shares
                await self.session.rollback()
                raise ConflictError(
                    f"这笔记录会让该基金在后续日期缺少 {missing:.4f} 份，"
                    "请按时间顺序补录，或先撤销之后受影响的记录"
                )

        await self.session.commit()
        await self.session.refresh(primary)
        return await self._to_read(primary)

    async def _create_transfer(
        self, user_id: int, fund: Fund, target: Fund | None, payload: FlowCreate
    ) -> tuple[FundPortfolioFlow, list[FundPortfolioFlow]]:
        """一笔转换写两条配对流水，两侧各自保留实际成交数据。

        字段口径统一为"`code` 指当前基金，`target_*` 指对手基金"：

        - `convert_out`：`shares_delta` 是转出份额，`target_shares` 是转入份额；
        - `convert_in`：`shares_delta` 是转入本基金的份额，`target_shares` 是对方转出份额。

        两个入口填写同样的事实，必须生成同样的两条记录。
        缺份额时只用**本侧**的金额与净值推算；两侧都缺就拒绝——
        复制另一侧的份额只有在两只基金净值恰好相等时才成立。
        """
        assert target is not None  # schema 已保证转换必须有对手基金
        out_shares: Decimal | None
        in_shares: Decimal | None
        out_nav: Decimal | None
        in_nav: Decimal | None
        out_cash: Decimal | None
        in_cash: Decimal | None
        out_fund: Fund
        in_fund: Fund
        if payload.kind == "convert_out":
            out_fund, in_fund = fund, target
            out_shares = abs(payload.shares_delta or Decimal(0))
            out_nav, out_cash = payload.nav, payload.cash_amount
            in_shares = payload.target_shares
            in_nav, in_cash = payload.target_nav, payload.target_cash_amount
        else:
            out_fund, in_fund = target, fund
            in_shares = abs(payload.shares_delta or Decimal(0))
            in_nav, in_cash = payload.nav, payload.cash_amount
            out_shares = payload.target_shares
            out_nav, out_cash = payload.target_nav, payload.target_cash_amount

        if out_shares is None:
            if out_cash and out_nav:
                out_shares = (Decimal(out_cash) / Decimal(out_nav)).quantize(SHARE_STEP)
            else:
                raise ValidationError("转换缺少转出份额：请填写转出份额，或转出金额与净值")
        if in_shares is None:
            if in_cash and in_nav:
                in_shares = (Decimal(in_cash) / Decimal(in_nav)).quantize(SHARE_STEP)
            else:
                raise ValidationError(
                    "转换缺少转入份额：请填写转入份额，或转入金额与净值（不能直接沿用转出份额）"
                )
        out_shares = Decimal(out_shares)
        in_shares = Decimal(in_shares)
        if out_shares <= 0 or in_shares <= 0:
            raise ValidationError("转换两侧的份额都必须大于零")

        platform = await self._resolve_platform(
            user_id, out_fund.id, payload.effective_on, payload.platform
        )
        cost, missing = await self._consumed_cost(
            user_id, out_fund.id, payload.effective_on, out_shares, platform
        )
        if missing > 0 or cost <= 0:
            raise ValidationError("转出份额超过该日期可用份额，请先核对买入记录")

        # 金额缺一侧时按"本侧份额 × 本侧净值"补，最后才用另一侧金额；
        # 两侧金额本来就允许不同（费用、到账差异），不能统一成转出金额。
        if not out_cash:
            out_cash = out_shares * Decimal(out_nav) if out_nav else cost
        out_cash = Decimal(out_cash)
        if not in_cash:
            in_cash = in_shares * Decimal(in_nav) if in_nav else out_cash
        in_cash = Decimal(in_cash)

        group = uuid.uuid4().hex
        out_flow = FundPortfolioFlow(
            user_id=user_id,
            fund_id=out_fund.id,
            kind="convert_out",
            effective_on=payload.effective_on,
            shares_delta=-out_shares,
            # 毛额是源侧转出，净额是目标侧实际到账：差额就是转换费用/损耗
            cash_amount=out_cash,
            net_amount=in_cash,
            nav=out_nav,
            target_fund_id=in_fund.id,
            transfer_group=group,
            platform=platform,
            note=payload.note,
        )
        in_flow = FundPortfolioFlow(
            user_id=user_id,
            fund_id=in_fund.id,
            kind="convert_in",
            effective_on=payload.effective_on,
            shares_delta=in_shares,
            cash_amount=in_cash,
            nav=in_nav,
            target_fund_id=out_fund.id,
            transfer_group=group,
            platform=platform,
            note=payload.note,
        )
        primary = out_flow if payload.kind == "convert_out" else in_flow
        return primary, [out_flow, in_flow]

    async def _to_read(self, flow: FundPortfolioFlow) -> FlowRead:
        row = (
            await self.session.execute(select(Fund.code, Fund.name).where(Fund.id == flow.fund_id))
        ).one()
        target_code = None
        if flow.target_fund_id:
            target_code = (
                await self.session.execute(select(Fund.code).where(Fund.id == flow.target_fund_id))
            ).scalar_one_or_none()
        return FlowRead(
            id=flow.id,
            code=row[0],
            fund_name=row[1],
            kind=flow.kind,
            kind_label=FLOW_KIND_LABELS.get(flow.kind, flow.kind),
            effective_on=flow.effective_on,
            cash_amount=float(flow.cash_amount) if flow.cash_amount is not None else None,
            net_amount=float(flow.net_amount) if flow.net_amount is not None else None,
            shares_delta=float(flow.shares_delta) if flow.shares_delta is not None else None,
            nav=float(flow.nav) if flow.nav is not None else None,
            ratio=float(flow.ratio) if flow.ratio is not None else None,
            target_code=target_code,
            platform=flow.platform,
            note=flow.note,
            created_at=flow.created_at,
        )

    async def delete_flow(self, user_id: int, flow_id: int) -> None:
        """软删除公司行为：删掉之后不能让后续记录变成负份额，也不能被旧请求复活。"""
        await self._lock(user_id)
        flow = (
            await self.session.execute(
                select(FundPortfolioFlow)
                .where(
                    FundPortfolioFlow.id == flow_id,
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.deleted_at.is_(None),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if flow is None:
            raise NotFoundError("流水不存在")

        targets = [flow]
        if flow.transfer_group:
            # 转换的转出/转入必须成对删除，否则会留下单边份额
            grouped = (
                (
                    await self.session.execute(
                        select(FundPortfolioFlow).where(
                            FundPortfolioFlow.user_id == user_id,
                            FundPortfolioFlow.transfer_group == flow.transfer_group,
                            FundPortfolioFlow.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            targets = list(grouped)

        removing = {row.id for row in targets}
        fund_ids = {row.fund_id for row in targets}
        fund_ids |= {row.target_fund_id for row in targets if row.target_fund_id}
        for fund_id in fund_ids:
            state = await self._state(user_id, fund_id, exclude_flow_ids=removing)
            if state.shortfall > 0 or state.shares < 0 or state.cost < 0:
                missing = state.shortfall or -state.shares
                raise ConflictError(
                    f"删除后该基金份额不足（缺 {missing:.4f} 份），"
                    "请先倒序撤销依赖这笔记录的后续记录"
                )

        deleted_at = datetime.now()
        for row in targets:
            # 保留墓碑：request_key 与 request_hash 留在库里，
            # 同一个请求重试会被 add_flow 识别为"已删除"而不是重新入账。
            row.deleted_at = deleted_at
        await self.session.commit()

    # ---------------------------------------------------------- 收益核对
    async def reconcile(self, user_id: int) -> ReconciliationResult:
        """用同一套账本重放核对：回执流水一列、公司行为影响一列、合计一列。"""
        rows = (
            await self.session.execute(
                select(FundTransaction, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundTransaction.fund_id)
                .where(
                    FundTransaction.user_id == user_id,
                    FundTransaction.deleted_at.is_(None),
                )
                .order_by(FundTransaction.confirmed_on, FundTransaction.id)
            )
        ).all()
        flow_rows = (
            await self.session.execute(
                select(FundPortfolioFlow, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundPortfolioFlow.fund_id)
                .where(
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.deleted_at.is_(None),
                )
                .order_by(FundPortfolioFlow.effective_on, FundPortfolioFlow.id)
            )
        ).all()

        transactions: dict[int, list] = defaultdict(list)
        flows: dict[int, list] = defaultdict(list)
        meta: dict[int, tuple[str, str]] = {}
        for tx, code, name in rows:
            transactions[tx.fund_id].append(tx)
            meta[tx.fund_id] = (code, name)
        for flow, code, name in flow_rows:
            flows[flow.fund_id].append(flow)
            meta.setdefault(flow.fund_id, (code, name))

        funds: list[ReconciliationFund] = []
        invested = redeemed = realized = dividends = Decimal(0)
        for fund_id in sorted(meta, key=lambda key: meta[key][0]):
            code, name = meta[fund_id]
            fund_flows = flows.get(fund_id, [])
            base = replay(transactions.get(fund_id, []), [])
            full = replay(transactions.get(fund_id, []), fund_flows)
            delta = full.shares - base.shares
            cash = sum((flow.cash_amount or Decimal(0) for flow in fund_flows), Decimal(0))
            funds.append(
                ReconciliationFund(
                    code=code,
                    name=name,
                    ledger_shares=float(base.shares),
                    ledger_cost=_money(base.cost),
                    flow_shares_delta=float(delta),
                    flow_cash=_money(cash),
                    expected_shares=float(full.shares),
                    note="含拆分 / 再投 / 转换调整" if delta else None,
                )
            )
            invested += full.bought
            redeemed += full.sold
            dividends += full.dividends
            realized += full.realized - full.dividends

        return ReconciliationResult(
            funds=funds,
            invested=_money(invested),
            redeemed=_money(redeemed),
            dividends=_money(dividends),
            realized_profit=_money(realized),
            generated_at=datetime.now(),
        )

    # ---------------------------------------------------------- 导出
    async def export_rows(self, user_id: int) -> list[dict[str, str]]:
        """导出原始账本：一行一笔，买卖与公司行为分开标注。"""
        rows: list[dict[str, str]] = []
        tx_rows = (
            await self.session.execute(
                select(FundTransaction, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundTransaction.fund_id)
                .where(
                    FundTransaction.user_id == user_id,
                    FundTransaction.deleted_at.is_(None),
                )
                .order_by(FundTransaction.confirmed_on, FundTransaction.id)
            )
        ).all()
        for tx, code, name in tx_rows:
            rows.append(
                {
                    "type": "trade",
                    "date": tx.confirmed_on.isoformat(),
                    "code": code,
                    "name": name,
                    "kind": tx.kind,
                    "quantity": str(tx.shares),
                    "nav": str(tx.nav),
                    "amount": str(tx.amount),
                    "fee": str(tx.fee),
                    "cash": str(tx.cash_amount),
                    "status": tx.status,
                    "source": tx.record_source,
                    "note": tx.note or "",
                }
            )
        flow_rows = (
            await self.session.execute(
                select(FundPortfolioFlow, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundPortfolioFlow.fund_id)
                .where(
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.deleted_at.is_(None),
                )
                .order_by(FundPortfolioFlow.effective_on, FundPortfolioFlow.id)
            )
        ).all()
        for flow, code, name in flow_rows:
            rows.append(
                {
                    "type": "flow",
                    "date": flow.effective_on.isoformat(),
                    "code": code,
                    "name": name,
                    "kind": flow.kind,
                    "quantity": str(flow.shares_delta or ""),
                    "nav": str(flow.nav or ""),
                    "amount": str(flow.cash_amount or ""),
                    "net_amount": str(flow.net_amount or ""),
                    "fee": "",
                    "cash": str(flow.cash_amount or ""),
                    "status": "recorded",
                    "source": "manual",
                    "note": flow.note or "",
                }
            )
        rows.sort(key=lambda item: item["date"])
        return rows


__all__ = ["PortfolioToolsService"]
