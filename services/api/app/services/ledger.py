"""统一的账本重放：把买卖流水与公司行为按时间合成持仓。

为什么要"重放"而不是继续读流水行上的 `remaining_shares`：

- 流水行里的余额是**确认当时**的快照。事后补录拆分、分红再投或用转换调整，
  这些快照就过期了；
- 卖出校验、可卖份额、FIFO 持有批次、已实现收益必须基于**同一份**重放结果，
  否则会出现"核对页显示 1000 份、卖出却只认 500 份"。

事件顺序：同一日期内先处理买卖流水，再处理公司行为（拆分/再投通常按日终生效）。

**分平台口径**（本模块的核心约束）：

1. 先对**全部平台**做一次完整重放，得到每个平台各自的份额/成本/批次；
2. 需要单平台结果时，在最后**投影**出该平台，而不是只把该平台的流水喂进来重算。

第 2 步很关键：旧实现按平台过滤事件后重放，导致一笔"全基金再投"会在
A、B 两个平台各加一次，各自算出 110 份可卖——合计 220 份，凭空多出 10 份。
现在公司行为带 `platform` 字段，只落到一个平台；拆分按比例作用于所有平台，
投影后各平台份额之和必然等于全基金份额。

公司行为缺平台（历史数据）时按"当日份额最大的平台"归属，规则固定、可复现，
不会随查询参数漂移。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SHARE_STEP = Decimal("0.0001")
CENT = Decimal("0.01")
ZERO = Decimal(0)
# 公司行为没有平台时的兜底桶名（历史数据）
UNASSIGNED = ""


@dataclass
class Lot:
    """一个持仓批次：份额、剩余成本、建仓日（含持有期起点）与平台。"""

    shares: Decimal
    cost: Decimal
    opened_on: date
    platform: str
    # 持有期起点：优先用平台确认日/公开规则推算日，缺失时用净值日
    since: date | None = None
    # 买入流水 ID，供费用明细回溯；再投/转入为 None
    source_id: int | None = None


@dataclass
class _Bucket:
    """单个平台的持仓状态（成本按平台移动平均结转）。"""

    shares: Decimal = ZERO
    cost: Decimal = ZERO
    realized: Decimal = ZERO
    dividends: Decimal = ZERO
    bought: Decimal = ZERO
    sold: Decimal = ZERO
    fees: Decimal = ZERO
    lots: list[Lot] = field(default_factory=list)


@dataclass
class LedgerState:
    shares: Decimal = ZERO
    cost: Decimal = ZERO
    realized: Decimal = ZERO
    dividends: Decimal = ZERO
    bought: Decimal = ZERO
    sold: Decimal = ZERO
    fees: Decimal = ZERO
    shortfall: Decimal = ZERO
    lots: list[Lot] = field(default_factory=list)
    # 各平台份额快照（不受 platform 投影影响）：用于"公司行为归属哪个平台"判断
    platform_shares: dict[str, Decimal] = field(default_factory=dict)

    @property
    def average_cost(self) -> Decimal | None:
        return self.cost / self.shares if self.shares else None


def _shares(value: Decimal) -> Decimal:
    return value.quantize(SHARE_STEP, rounding=ROUND_HALF_UP)


def _consume(lots: list[Lot], shares: Decimal) -> tuple[Decimal, Decimal]:
    """按先进先出消耗份额，返回（消耗成本, 不足份额）。"""
    left = shares
    cost = ZERO
    while left > 0 and lots:
        lot = lots[0]
        if lot.shares <= 0:
            lots.pop(0)
            continue
        used = min(left, lot.shares)
        portion = lot.cost * used / lot.shares
        lot.shares -= used
        lot.cost -= portion
        cost += portion
        left -= used
        if lot.shares <= SHARE_STEP / 2:
            lots.pop(0)
    return cost, left


def _exit_cost(cost: Decimal, shares: Decimal, exited: Decimal) -> Decimal:
    """按移动平均结转卖出/转出成本；全部退出时结转剩余全部成本。"""
    if shares <= 0:
        return ZERO
    if exited >= shares:
        return cost
    # 与确认时的口径一致：分摊成本四舍五入到分，避免核对时出现 1817.9959 这种尾差
    return (cost * exited / shares).quantize(CENT, rounding=ROUND_HALF_UP)


def _flow_platform(payload: Any) -> str:
    value = getattr(payload, "platform", None)
    return (value or "").strip()


def _pick_platform(buckets: dict[str, _Bucket]) -> str:
    """历史数据没有平台时，取份额最大的平台；并列取字典序最小，保证可复现。"""
    held = [(key, value.shares) for key, value in buckets.items() if value.shares > 0]
    if not held:
        return UNASSIGNED
    return sorted(held, key=lambda item: (-item[1], item[0]))[0][0]


def _add_lot(
    bucket: _Bucket,
    shares: Decimal,
    cost: Decimal,
    day: date,
    since: date,
    *,
    platform: str,
) -> None:
    if shares <= 0:
        return
    bucket.shares += shares
    bucket.cost += cost
    bucket.lots.append(Lot(shares=shares, cost=cost, opened_on=day, platform=platform, since=since))


def replay(
    transactions: Sequence,
    flows: Sequence = (),
    *,
    until: date | None = None,
    platform: str | None = None,
) -> LedgerState:
    """按日期重放流水与公司行为，返回持仓状态。

    参数：
        transactions: 同一基金的 `FundTransaction` 列表（已确认、未作废）。
        flows: 同一基金的 `FundPortfolioFlow` 列表。
        until: 只重放到该日期（含），用于"卖出当日可用份额"。
        platform: 只取该平台的投影结果；None 表示全部平台汇总。

    无论是否指定 `platform`，内部都先重放**全部平台**再投影，
    这样"各平台份额之和"恒等于"全基金份额"。
    """
    # 流水与公司行为是两种 ORM 对象，这里只按公共字段读取，用 Any 避免联合类型噪音
    events: list[tuple[date, int, Any]] = []
    for row in transactions:
        if getattr(row, "status", "confirmed") != "confirmed":
            continue
        if getattr(row, "voided_at", None) is not None:
            continue
        day = row.confirmed_on
        if until is not None and day > until:
            continue
        events.append((day, 0, row))

    for flow in flows:
        day = flow.effective_on
        if until is not None and day > until:
            continue
        events.append((day, 1, flow))

    events.sort(key=lambda item: (item[0], item[1], getattr(item[2], "id", 0) or 0))

    buckets: dict[str, _Bucket] = {}
    shortfall = ZERO
    # 转换两侧是一对：转入侧的实际金额才是"换回来的价值"，
    # 用它和转出成本比较，转换损耗（费用/到账差）才会体现在收益里。
    paired_in_cash: dict[str, Decimal] = {}
    for flow in flows:
        group = getattr(flow, "transfer_group", None)
        if group and getattr(flow, "kind", "") == "convert_in":
            paired_in_cash[group] = Decimal(flow.cash_amount or 0)

    def bucket(key: str) -> _Bucket:
        return buckets.setdefault(key, _Bucket())

    for day, order, payload in events:
        if order == 0:  # 买卖流水
            kind = payload.kind
            key = (getattr(payload, "platform", None) or "").strip()
            if kind == "sell" and buckets.get(key) is None:
                # 未填平台或该平台没见过持仓：只有一个平台持有才能归它
                held = [name for name, value in buckets.items() if value.shares > 0]
                if len(held) == 1:
                    key = held[0]
            entry = bucket(key)
            shares = Decimal(payload.shares)
            if kind == "buy":
                raw_cost = getattr(payload, "cash_amount", None)
                if raw_cost is None:
                    raw_cost = getattr(payload, "amount", None)
                if raw_cost is None:
                    raw_cost = shares * Decimal(getattr(payload, "nav", 0) or 0)
                cost = Decimal(raw_cost)
                basis = getattr(payload, "calculation_basis", None) or {}
                predicted = basis.get("expected_confirm_on")
                since = (
                    getattr(payload, "settled_on", None)
                    or (date.fromisoformat(predicted) if predicted else None)
                    or payload.confirmed_on
                )
                entry.shares += shares
                entry.cost += cost
                entry.bought += cost
                entry.fees += Decimal(getattr(payload, "fee", 0) or 0)
                entry.lots.append(
                    Lot(
                        shares=shares,
                        cost=cost,
                        opened_on=day,
                        platform=key,
                        since=since,
                        source_id=payload.id,
                    )
                )
            else:
                allocated = _exit_cost(entry.cost, entry.shares, shares)
                shortfall += _consume(entry.lots, shares)[1]
                entry.shares -= shares
                entry.cost = entry.cost - allocated if entry.shares > 0 else ZERO
                proceeds = getattr(payload, "cash_amount", None)
                if proceeds is None:
                    proceeds = shares * Decimal(getattr(payload, "nav", 0) or 0) - Decimal(
                        getattr(payload, "fee", 0) or 0
                    )
                entry.realized += Decimal(proceeds) - allocated
                entry.sold += Decimal(proceeds)
                entry.fees += Decimal(getattr(payload, "fee", 0) or 0)
            continue

        kind = payload.kind
        if kind == "split":
            ratio = Decimal(payload.ratio or 0)
            delta = Decimal(payload.shares_delta or 0)
            total = sum((value.shares for value in buckets.values()), ZERO)
            if ratio > 0:
                # 拆分/合并是基金级事件：所有平台按同一比例缩放，成本不变
                for value in buckets.values():
                    if value.shares:
                        value.shares = _shares(value.shares * ratio)
                        for lot in value.lots:
                            lot.shares = _shares(lot.shares * ratio)
            elif delta and total > 0:
                for value in buckets.values():
                    if value.shares <= 0:
                        continue
                    grown = _shares(value.shares + delta * value.shares / total)
                    scale = grown / value.shares if value.shares else ZERO
                    value.shares = grown
                    for lot in value.lots:
                        lot.shares = _shares(lot.shares * scale)
            continue

        key = _flow_platform(payload) or _pick_platform(buckets)
        entry = bucket(key)

        if kind == "dividend":
            cash = Decimal(payload.cash_amount or 0)
            entry.dividends += cash
            entry.realized += cash
        elif kind == "reinvest":
            shares = Decimal(payload.shares_delta or 0)
            cash = Decimal(payload.cash_amount or 0)
            if cash <= 0 and payload.nav:
                cash = shares * Decimal(payload.nav)
            if cash < 0:
                cash = ZERO
            # 再投 = 收到红利 + 用这笔钱买入：红利计入已实现收益，成本计入持仓。
            # 少算这一步，总收益会凭空少掉再投金额。
            # 不并入 `dividends`：那个字段专门表示"现金分红"，再投拿到的是份额。
            entry.realized += cash
            _add_lot(entry, shares, cash, day, day, platform=key)
        elif kind == "convert_out":
            shares = abs(Decimal(payload.shares_delta or 0))
            allocated = _exit_cost(entry.cost, entry.shares, shares)
            shortfall += _consume(entry.lots, shares)[1]
            entry.shares -= shares
            entry.cost = entry.cost - allocated if entry.shares > 0 else ZERO
            group = getattr(payload, "transfer_group", None)
            # 优先用净额：转出 100、目标只到账 90 时，那 10 元是转换费用/损耗，
            # 必须计入已实现收益，不能凭空消失。
            # 净额缺失时（老数据）退回配对转入侧的金额，再退回自己的毛额。
            proceeds = Decimal(getattr(payload, "net_amount", None) or 0)
            if proceeds <= 0:
                proceeds = paired_in_cash.get(group or "", ZERO)
            if proceeds <= 0:
                proceeds = Decimal(payload.cash_amount or 0)
            if proceeds <= 0 and payload.nav:
                proceeds = shares * Decimal(payload.nav)
            if proceeds > 0:
                entry.realized += proceeds - allocated
        elif kind == "convert_in":
            shares = Decimal(payload.shares_delta or 0)
            cash = Decimal(payload.cash_amount or 0)
            if cash <= 0 and payload.nav:
                cash = shares * Decimal(payload.nav)
            _add_lot(entry, shares, cash if cash > 0 else ZERO, day, day, platform=key)

    # 投影：指定平台只取该平台，否则汇总全部平台
    if platform is None:
        selected = list(buckets.values())
    else:
        only = buckets.get(platform)
        selected = [only] if only is not None else []

    state = LedgerState(
        shortfall=shortfall,
        platform_shares={
            key: _shares(value.shares) for key, value in buckets.items() if value.shares
        },
    )
    for item in selected:
        state.shares += item.shares
        state.cost += item.cost
        state.realized += item.realized
        state.dividends += item.dividends
        state.bought += item.bought
        state.sold += item.sold
        state.fees += item.fees
        state.lots.extend(item.lots)
    state.shares = _shares(state.shares)
    state.lots = [lot for lot in state.lots if lot.shares > 0]
    return state


def exit_cost(state: LedgerState, shares: Decimal) -> tuple[Decimal, Decimal]:
    """计算转出份额对应的成本与不足份额（与卖出同一口径，不修改状态）。"""
    missing = shares - state.shares if shares > state.shares else ZERO
    return _exit_cost(state.cost, state.shares, shares), missing


def lot_snapshots(state: LedgerState) -> list[dict[str, object]]:
    """给费用计算用的批次视图（保持 FIFO 顺序）。"""
    return [
        {
            "shares": lot.shares,
            "cost": lot.cost,
            "since": lot.since or lot.opened_on,
            "platform": lot.platform,
            "id": lot.source_id,
        }
        for lot in state.lots
        if lot.shares > 0
    ]


__all__ = [
    "SHARE_STEP",
    "UNASSIGNED",
    "LedgerState",
    "Lot",
    "exit_cost",
    "lot_snapshots",
    "replay",
]
