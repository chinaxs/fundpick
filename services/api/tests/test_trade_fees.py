"""公开费率解析、申购外扣法、赎回先进先出和未知费用保护。"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.datasources.fund_fees import parse_fee_page
from app.services.trade_fee_math import fee_for, matches, redemption_fee

RULES = [
    {"kind": "buy", "condition": "小于100万元", "standard": "1.50%", "discounted": "0.15%"},
    {"kind": "buy", "condition": "大于等于100万元", "standard": "每笔1000元", "discounted": ""},
    {"kind": "sell", "condition": "小于7天", "standard": "1.50%", "discounted": ""},
    {"kind": "sell", "condition": "大于等于7天", "standard": "0.50%", "discounted": ""},
    {"kind": "confirmation", "condition": "买入确认日", "standard": "T+1", "discounted": ""},
    {"kind": "confirmation", "condition": "卖出确认日", "standard": "T+1", "discounted": ""},
]


def test_parser_only_uses_trade_fees_and_preserves_source_discounts():
    html = """<h4 class="t">运作费用</h4>
    <table><tbody><tr><td>管理费</td><td>1.5%</td></tr></tbody></table>
    <h4 class="t">申购费率（前端）</h4>
    <table><tbody><tr><td>小于100万元</td><td><strike>1.50%</strike>
    | 0.15%</td></tr></tbody></table>
    <h4 class="t">赎回费率</h4>
    <table><tbody><tr><td>小于7天</td><td>1.50%</td></tr></tbody></table>"""
    assert parse_fee_page(html) == [RULES[0], RULES[2]]


def test_buy_external_fee_formula_platform_discount_and_fixed_bracket():
    assert fee_for(RULES, "buy", Decimal(1000), Decimal(1000), "")[0] == Decimal("14.78")
    assert fee_for(RULES, "buy", Decimal(1000), Decimal(1000), "天天基金")[0] == Decimal("1.50")
    assert fee_for(RULES, "buy", Decimal(1000000), Decimal(1000000), "")[0] == Decimal(1000)
    assert (
        fee_for(RULES, "buy", Decimal(1000), Decimal(1000), "支付宝")[1]["rate_type"]
        == "公开标准费率"
    )


def test_unknown_does_not_mean_zero_and_amount_boundaries():
    assert not matches("小于100万元", Decimal(1000000))
    assert matches("大于等于100万元，小于500万元", Decimal(1000000))
    assert not matches("持有时间较短", Decimal(2))
    assert fee_for([], "buy", Decimal(1), Decimal(1), "") is None
    assert fee_for([RULES[0], RULES[0]], "buy", Decimal(1), Decimal(1), "") is None
    assert fee_for([{**RULES[0], "standard": "---"}], "buy", Decimal(1), Decimal(1), "") is None


def row(id, kind, shares, since, platform="A"):
    return SimpleNamespace(
        id=id,
        kind=kind,
        shares=Decimal(shares),
        confirmed_on=since,
        settled_on=since,
        platform=platform,
        status="confirmed",
    )


def test_redemption_matches_each_fifo_batch_including_previous_sale():
    rows = [
        row(1, "buy", "100", date(2026, 1, 1)),
        row(2, "buy", "100", date(2026, 1, 9)),
        row(3, "sell", "30", date(2026, 1, 10)),
    ]
    fee, details = redemption_fee(RULES, rows, Decimal(100), date(2026, 1, 11), Decimal(2), "A")
    assert fee == Decimal("1.60")  # 70份长持仓*2*0.5% + 30份短持仓*2*1.5%
    assert [d["shares"] for d in details] == ["70", "30"]
    assert [d["days"] for d in details] == [10, 2]
    assert redemption_fee(RULES, rows, Decimal(200), date(2026, 1, 11), Decimal(2), "A") is None
    assert redemption_fee(RULES, rows, Decimal(1), date(2026, 1, 11), Decimal(2), "B") is None


def test_year_brackets_use_anniversary_not_fixed_365_days():
    since = date(2023, 3, 1)
    assert matches("小于1年", Decimal(365), since, date(2024, 2, 29))
    assert not matches("大于等于1年", Decimal(365), since, date(2024, 2, 29))
    assert matches("大于等于1年", Decimal(366), since, date(2024, 3, 1))


def test_parse_confirmation_cycles_separately_from_fees():
    html = (
        '<h4 class="t">交易确认日</h4><table><tr><th>买入确认日</th><td>T+1</td></tr>'
        "<tr><th>卖出确认日</th><td>T+2</td></tr></table>"
    )
    assert parse_fee_page(html) == [
        {"kind": "confirmation", "condition": "买入确认日", "standard": "T+1", "discounted": ""},
        {"kind": "confirmation", "condition": "卖出确认日", "standard": "T+2", "discounted": ""},
    ]
