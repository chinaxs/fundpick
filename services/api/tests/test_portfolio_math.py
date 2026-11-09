"""成交计算：费用、部分卖出成本和清仓尾差。"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationError
from app.schemas.portfolio import TradeInput
from app.services.portfolio_math import Balance, calculate


def trade(kind="buy", **values):
    return TradeInput(code="000001", kind=kind, confirmed_on=date(2026, 1, 1), **values)


def test_fee_and_downward_rounding():
    result = calculate(trade(amount="1000", fee="10"), Decimal("3"), Balance())
    assert result["shares"] == Decimal("330.0000")
    assert result["remaining_cost"] == Decimal("1000")
    result = calculate(trade(amount="1000"), Decimal("3"), Balance())
    assert result["shares"] == Decimal("333.3333")


def test_partial_sell_and_full_exit():
    state = Balance(shares=Decimal("750"), cost=Decimal("2010"))
    result = calculate(trade("sell", shares="300", fee="5"), Decimal("5"), state)
    assert result["cash_amount"] == Decimal("1495")
    assert result["realized_profit"] == Decimal("691")
    assert result["remaining_shares"] == Decimal("450")
    assert result["remaining_cost"] == Decimal("1206")
    state = Balance(shares=Decimal("0.3333"), cost=Decimal("1.01"))
    result = calculate(trade("sell", shares="0.3333"), Decimal("4"), state)
    assert result["remaining_cost"] == result["remaining_shares"] == 0
    assert result["realized_profit"] == Decimal("0.32")


@pytest.mark.parametrize(
    "payload,nav,state",
    [
        (trade(amount="10", fee="10"), "1", Balance()),
        (trade(amount="0.01"), "1000000", Balance()),
        (trade("sell", shares="1"), "1", Balance()),
        (trade("sell", shares="1", fee="2"), "1", Balance(shares=Decimal(1))),
    ],
)
def test_invalid_economic_input(payload, nav, state):
    with pytest.raises(ValidationError):
        calculate(payload, Decimal(nav), state)
