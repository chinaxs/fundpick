"""连续操作验收：每次写入后核对组合资金守恒、份额与各读取入口。

纳入默认回归；同时覆盖有费用/无费用、全额/部分转换、双平台、再投与卖出。
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from acceptance_rework import audit_book as audit_book
from acceptance_rework import book as book
from acceptance_rework import flow, overview, purchase
from acceptance_rework import target_fund as imported_target_fund
from test_portfolio_flow import BASE, DAY, commit

base_target_fund = imported_target_fund


@pytest.fixture
async def target_fund(base_target_fund, audit_book):
    """先清理本矩阵在对手基金上新增的买卖/申请，再交给原fixture删除基金。"""
    yield base_target_fund
    from sqlalchemy import delete, select

    from app.db.session import async_session_factory
    from app.models.fund import Fund
    from app.models.fund_transaction import FundTransaction
    from app.models.trade_application import TradeApplication

    async with async_session_factory() as session:
        fund_id = await session.scalar(select(Fund.id).where(Fund.code == base_target_fund))
        for model in (FundTransaction, TradeApplication):
            await session.execute(
                delete(model).where(
                    model.user_id == audit_book["user_id"], model.fund_id == fund_id
                )
            )
        await session.commit()


async def assert_consistent(client, account):
    data = await overview(client, account)
    summary = data["summary"]
    assert all(item["shares"] >= 0 and item["remaining_cost"] >= 0 for item in data["holdings"])
    expected = (
        Decimal(str(summary["total_market_value"]))
        + Decimal(str(summary["total_sell_amount"]))
        + Decimal(str(summary["total_dividends"]))
        - Decimal(str(summary["total_buy_amount"]))
    )
    assert abs(Decimal(str(summary["total_return"])) - expected) <= Decimal("0.01"), data
    held = (await client.get(BASE + "/holding-codes", headers=account["headers"])).json()["data"]
    assert sorted(held) == sorted(item["code"] for item in data["holdings"] if item["shares"] > 0)
    ai = (await client.get(BASE + "/portfolio/ai-context", headers=account["headers"])).json()[
        "data"
    ]
    positions = {item["code"]: item for item in ai["positions"]}
    for item in data["holdings"]:
        if item["shares"] == 0 and item["code"] not in positions:
            continue
        assert abs(positions[item["code"]]["shares"] - item["shares"]) < 0.00001
        assert abs(positions[item["code"]]["realized_profit"] - item["realized_profit"]) < 0.011
    reconciliation = (
        await client.get(BASE + "/portfolio/reconciliation", headers=account["headers"])
    ).json()["data"]
    assert {item["code"]: item["expected_shares"] for item in reconciliation["funds"]} == {
        item["code"]: item["shares"] for item in data["holdings"]
    }
    return data


@pytest.mark.parametrize("direction", ["convert_out", "convert_in"])
@pytest.mark.parametrize("fraction", ["0.5", "1"])
@pytest.mark.parametrize("charge", ["0", "3.25"])
async def test_conversion_then_partial_and_full_sale(
    client, audit_book, target_fund, direction, fraction, charge
):
    await purchase(client, audit_book, platform="A", amount="200", nav="2")
    out_shares = Decimal(100) * Decimal(fraction)
    gross = out_shares * 2
    net = gross - Decimal(charge)
    # 目标净值1元，份额与净转入金额相等；从两个方向填写同样事实。
    if direction == "convert_out":
        payload = {
            "code": audit_book["code"],
            "shares_delta": str(-out_shares),
            "nav": "2",
            "cash_amount": str(gross),
            "target_code": target_fund,
            "target_shares": str(net),
            "target_nav": "1",
            "target_cash_amount": str(net),
        }
    else:
        payload = {
            "code": target_fund,
            "shares_delta": str(net),
            "nav": "1",
            "cash_amount": str(net),
            "target_code": audit_book["code"],
            "target_shares": str(out_shares),
            "target_nav": "2",
            "target_cash_amount": str(gross),
        }
    response = await client.post(
        BASE + "/portfolio/flows",
        headers=audit_book["headers"],
        json={
            **payload,
            "kind": direction,
            "platform": "A",
            "effective_on": str(DAY + timedelta(days=1)),
            "request_key": str(uuid4()),
        },
    )
    assert response.status_code == 201, response.text
    await assert_consistent(client, audit_book)
    left = net
    for offset, shares in [(2, Decimal("10")), (3, left - 10)]:
        await commit(
            client,
            audit_book,
            {
                "code": target_fund,
                "kind": "sell",
                "record_source": "estimated",
                "platform": "A",
                "shares": str(shares),
                "nav_mode": "manual",
                "nav": "1",
                "fee": "0.10",
                "confirmed_on": str(DAY + timedelta(days=offset)),
            },
        )
        await assert_consistent(client, audit_book)


async def test_multi_platform_dividend_reinvest_split_sale_and_conversion(
    client, audit_book, target_fund
):
    for platform, amount in [("A", "100"), ("B", "200")]:
        await purchase(client, audit_book, platform=platform, amount=amount)
    for platform, dividend in [("A", "5"), ("B", "10")]:
        await flow(client, audit_book, "dividend", platform=platform, cash_amount=dividend)
        await assert_consistent(client, audit_book)
    await flow(
        client, audit_book, "reinvest", platform="A", shares_delta="10", cash_amount="10", nav="1"
    )
    await assert_consistent(client, audit_book)
    await flow(client, audit_book, "split", ratio="2", effective_on=str(DAY + timedelta(days=2)))
    await assert_consistent(client, audit_book)
    await commit(
        client,
        audit_book,
        {
            "code": audit_book["code"],
            "kind": "sell",
            "record_source": "estimated",
            "platform": "A",
            "shares": "100",
            "nav_mode": "manual",
            "nav": "1",
            "fee": "0.50",
            "confirmed_on": str(DAY + timedelta(days=3)),
        },
    )
    await assert_consistent(client, audit_book)
    await flow(
        client,
        audit_book,
        "convert_out",
        platform="B",
        shares_delta="-100",
        cash_amount="100",
        target_code=target_fund,
        target_shares="95",
        target_cash_amount="95",
        target_nav="1",
        effective_on=str(DAY + timedelta(days=4)),
    )
    await assert_consistent(client, audit_book)


async def test_paired_conversion_deletion_restores_positions_and_cash(
    client, audit_book, target_fund
):
    await purchase(client, audit_book)
    before = await assert_consistent(client, audit_book)
    result = await flow(
        client,
        audit_book,
        "convert_out",
        shares_delta="-50",
        cash_amount="50",
        target_code=target_fund,
        target_shares="45",
        target_cash_amount="45",
        target_nav="1",
    )
    await assert_consistent(client, audit_book)
    deleted = await client.delete(
        BASE + f"/portfolio/flows/{result['id']}", headers=audit_book["headers"]
    )
    assert deleted.status_code == 200, deleted.text
    after = await assert_consistent(client, audit_book)
    assert after["summary"]["total_return"] == before["summary"]["total_return"]


async def test_auto_sell_of_conversion_only_fund_uses_existing_platform(
    client, audit_book, target_fund, monkeypatch
):
    from datetime import datetime
    from unittest.mock import AsyncMock

    from sqlalchemy import select
    from test_trade_fees import RULES

    from app.db.session import async_session_factory
    from app.models.fund import Fund
    from app.services import automatic_trade

    await purchase(client, audit_book, platform="A")
    await flow(
        client,
        audit_book,
        "convert_out",
        platform="A",
        shares_delta="-50",
        cash_amount="50",
        target_code=target_fund,
        target_shares="50",
        target_nav="1",
    )
    async with async_session_factory() as session:
        fund = await session.scalar(select(Fund).where(Fund.code == target_fund))
        fund.latest_nav_date = DAY + timedelta(days=2)
        await session.commit()
    monkeypatch.setattr(
        automatic_trade, "lookup_rules", AsyncMock(return_value=(RULES, "review", datetime.now()))
    )
    monkeypatch.setattr(automatic_trade, "lookup_nav", AsyncMock(return_value=1))
    response = await client.post(
        BASE + "/auto-transactions",
        headers=audit_book["headers"],
        json={
            "code": target_fund,
            "kind": "sell",
            "shares": "10",
            "pricing_rule": "auto",
            "submitted_at": str(DAY + timedelta(days=2)) + "T14:00:00+08:00",
            "request_key": str(uuid4()),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "recorded", (
        "仅转换转入、平台明确为A的持仓，自动卖出应能推断平台并入账，不能永远停在费用待核对"
    )
