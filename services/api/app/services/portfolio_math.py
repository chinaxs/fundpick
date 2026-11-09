"""模拟交易的 Decimal 计算：金额含费、移动平均成本、清仓尾差。"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from app.core.exceptions import ValidationError
from app.schemas.portfolio import TradeInput

ZERO = Decimal(0)
CENT = Decimal("0.01")
UNIT = Decimal("0.0001")


def money(value: Decimal) -> Decimal:
    """金额四舍五入到分；内部计算不经过浮点数。"""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Balance:
    shares: Decimal = ZERO
    cost: Decimal = ZERO
    realized: Decimal = ZERO
    bought: Decimal = ZERO
    sold: Decimal = ZERO
    fees: Decimal = ZERO


def balance_of(rows: Sequence[Any]) -> Balance:
    """输入按确认日、流水 ID 排序的同一基金有效流水。"""
    state = Balance()
    for row in rows:
        # 每笔快照属于该平台，组合用资金/份额变化汇总，避免混用不同平台成本。
        state.shares += row.shares if row.kind == "buy" else -row.shares
        state.cost += (
            row.cash_amount if row.kind == "buy" else -(row.cash_amount - row.realized_profit)
        )
        state.realized += row.realized_profit
        state.fees += row.fee
        if row.kind == "buy":
            state.bought += row.cash_amount
        else:
            state.sold += row.cash_amount
    return state


class BalanceLike(Protocol):
    """`calculate` 只读取可用份额与剩余成本，`ledger.LedgerState` 也满足。"""

    shares: Decimal
    cost: Decimal


def calculate(request: TradeInput, nav: Decimal, before: BalanceLike) -> dict[str, Decimal]:
    """买入金额含手续费，卖出按份额；全部卖出结转全部剩余成本。"""
    fee = money(request.fee)
    if request.kind == "buy":
        amount = money(request.amount or ZERO)
        if fee >= amount:
            raise ValidationError("买入手续费必须小于总金额")
        shares = (
            request.confirmed_shares
            if request.record_source == "receipt"
            else ((amount - fee) / nav).quantize(UNIT, rounding=ROUND_DOWN)
        )
        assert shares is not None
        if shares <= 0:
            raise ValidationError("金额不足以买入 0.0001 份，请调整金额")
        cash, profit = amount, ZERO
        cost, remaining = before.cost + cash, before.shares + shares
    else:
        shares = request.shares or ZERO
        if shares > before.shares:
            raise ValidationError(f"卖出份额超过可用份额 {before.shares:.4f}")
        amount = (
            money(request.received_amount + fee)
            if request.record_source == "receipt" and request.received_amount is not None
            else money(shares * nav)
        )
        if amount <= 0 or fee > amount:
            raise ValidationError("卖出金额需大于零，手续费不得超过卖出金额")
        cash = amount - fee
        allocated = (
            before.cost if shares == before.shares else money(before.cost * shares / before.shares)
        )
        profit = cash - allocated
        cost, remaining = before.cost - allocated, before.shares - shares
    return {
        "amount": amount,
        "fee": fee,
        "shares": shares,
        "cash_amount": cash,
        "realized_profit": profit,
        "remaining_shares": remaining,
        "remaining_cost": cost,
    }
