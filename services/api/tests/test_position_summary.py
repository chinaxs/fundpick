"""组合估值回归：缺失净值不能被计成全额亏损。"""

from datetime import date

import pytest

from app.schemas.portal_me import PositionItem
from app.services.portal_position import PositionService


def position(amount: float, market_value: float | None) -> PositionItem:
    """构造同成本净值的模拟记录，覆盖组合完整与部分估值。"""
    return PositionItem(
        id=1,
        code="000001",
        name="测试基金",
        type="stock",
        amount=amount,
        cost_nav=1,
        bought_at=date(2026, 1, 1),
        shares=amount,
        market_value=market_value,
    )


@pytest.mark.parametrize("missing_amount", [1000, 5000])
def test_partial_valuation_does_not_report_false_loss(missing_amount: float) -> None:
    summary = PositionService._summarize([position(1000, 1100), position(missing_amount, None)])
    assert summary.count == 2
    assert summary.valued_count == 1
    assert summary.total_amount == 1000 + missing_amount
    assert summary.total_market_value is None
    assert summary.total_profit is None
    assert summary.profit_rate is None


def test_complete_valuation_reports_weighted_profit() -> None:
    summary = PositionService._summarize([position(1000, 1100), position(3000, 2700)])
    assert summary.valued_count == summary.count == 2
    assert summary.total_amount == 4000
    assert summary.total_market_value == 3800
    assert summary.total_profit == -200
    assert summary.profit_rate == -5


@pytest.mark.parametrize("items", [[], [position(1000, None)]])
def test_unvalued_portfolio_has_no_profit(items: list[PositionItem]) -> None:
    summary = PositionService._summarize(items)
    assert summary.valued_count == 0
    assert summary.total_market_value is None
    assert summary.total_profit is None
    assert summary.profit_rate is None
