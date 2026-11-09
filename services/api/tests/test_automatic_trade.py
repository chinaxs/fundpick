"""只填金额与时间的自动计算：实际净值、公开费用、等待、重试和来源隔离。"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from test_portfolio_flow import BASE, DAY, portfolio
from test_portfolio_flow import book as book
from test_trade_fees import RULES


def request(book, **updates):
    return {
        "code": book["code"],
        "kind": "buy",
        "amount": "1000",
        "submitted_at": DAY.isoformat() + "T14:00:00+08:00",
        "pricing_rule": "auto",
        "request_key": str(uuid4()),
        **updates,
    }


async def auto(client, book, data):
    result = await client.post(BASE + "/auto-transactions", json=data, headers=book["headers"])
    assert result.status_code == 200, result.text
    return result.json()["data"]


@pytest.fixture(autouse=True)
def no_external_lookups():
    with (
        patch(
            "app.services.automatic_trade.lookup_rules",
            new=AsyncMock(
                return_value=(
                    RULES,
                    "https://fundf10.eastmoney.com/jjfl_test.html",
                    datetime(2026, 1, 1),
                )
            ),
        ),
        patch("app.services.automatic_trade.lookup_nav", new=AsyncMock(return_value=2)),
    ):
        yield


async def test_auto_buy_needs_only_time_money_and_is_idempotent(client, book):
    data = request(book)
    result = await auto(client, book, data)
    assert result["status"] == "recorded"
    trade = result["transaction"]
    assert trade["record_source"] == "estimated"
    assert trade["fee"] == 14.78
    assert trade["shares"] == 492.61
    assert trade["nav"] == 2
    assert trade["calculation_basis"]["fee_rules"][0]["rate"] == "1.50%"
    assert (await auto(client, book, data))["transaction"]["id"] == trade["id"]
    data = await portfolio(client, book)
    assert data["summary"]["estimated_count"] == 1
    assert data["summary"]["calculated_count"] == 0
    assert data["summary"]["pending_count"] == 0
    assert data["holdings"][0]["estimated_count"] == 1


async def test_discount_only_applies_to_named_source_platform(client, book):
    result = await auto(client, book, request(book, platform="天天基金"))
    assert result["transaction"]["fee"] == 1.50
    assert result["transaction"]["shares"] == 499.25


async def test_missing_fees_never_fills_zero_and_retry_calculates_later(client, book):
    with patch(
        "app.services.automatic_trade.lookup_rules",
        new=AsyncMock(return_value=([], "source", None)),
    ):
        data = request(book)
        result = await auto(client, book, data)
        assert result["status"] == "pending"
        assert "费率" in result["message"]
        assert (await portfolio(client, book))["holdings"] == []
    # 打开待处理清单会自动重试，仅针对用户选择自动处理的记录。
    result = await client.get(BASE + "/applications", headers=book["headers"])
    assert result.status_code == 200, result.text
    assert result.json()["data"] == []
    assert (await portfolio(client, book))["summary"]["estimated_count"] == 1


async def test_unpublished_nav_stays_pending(client, book):
    with patch("app.services.automatic_trade.lookup_nav", new=AsyncMock(return_value=None)):
        result = await auto(client, book, request(book))
    assert result["status"] == "pending"
    assert "官方净值" in result["message"]
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 0


async def test_auto_sell_uses_fifo_holding_period_and_does_not_double_deduct_management_fee(
    client, book
):
    await auto(client, book, request(book))
    sell = request(
        book,
        kind="sell",
        amount=None,
        shares="100",
        submitted_at=(DAY + timedelta(days=10)).isoformat() + "T14:00:00+08:00",
    )
    # 此后日期在测试基金最新净值日有本地同日净值；补查模拟值应写进本地。
    from app.db.session import async_session_factory
    from app.models.fund_nav import FundNav

    async with async_session_factory() as session:
        session.add(FundNav(fund_id=book["fund_id"], nav_date=DAY + timedelta(days=10), unit_nav=2))
        await session.commit()
    result = await auto(client, book, sell)
    assert result["status"] == "recorded", result
    assert result["transaction"]["fee"] == 1
    assert result["transaction"]["cash_amount"] == 199
    details = result["transaction"]["calculation_basis"]["fee_rules"]
    assert details[0]["days"] == 9
    assert details[0]["rate"] == "0.50%"


async def test_automatic_data_is_member_private(client, book):
    await auto(client, book, request(book))
    assert (await client.get(BASE + "/portfolio", headers=book["other"])).json()["data"][
        "holdings"
    ] == []
    assert (await client.get(BASE + "/applications", headers=book["other"])).json()["data"] == []


async def test_concurrent_automatic_retry_creates_one_record(client, book):
    data = request(book)
    results = await asyncio.gather(auto(client, book, data), auto(client, book, data))
    assert all(result["status"] == "recorded" for result in results), results
    assert results[0]["transaction"]["id"] == results[1]["transaction"]["id"]
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 1


async def test_public_t_plus_one_waits_through_weekend_even_with_nav(client, book):
    from zoneinfo import ZoneInfo

    class Friday(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 6, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    payload = request(book, submitted_at="2026-11-06T14:00:00+08:00")
    with patch("app.services.automatic_trade.datetime", Friday):
        result = await auto(client, book, payload)
    assert result["status"] == "pending"
    assert "2026-11-09" in result["message"]
    assert "T+1" in result["message"]
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 0


async def test_cancelled_auto_application_does_not_reenter_processing(client, book):
    with patch("app.services.automatic_trade.lookup_nav", new=AsyncMock(return_value=None)):
        result = await auto(client, book, request(book))
    id = result["application"]["id"]
    assert (
        await client.post(BASE + f"/applications/{id}/cancel", headers=book["headers"])
    ).status_code == 200
    assert (await client.get(BASE + "/applications", headers=book["headers"])).json()["data"] == []
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 0


async def test_voided_auto_trade_has_one_history_entry_and_delete_does_not_reveal_application(
    client, book
):
    payload = request(book)
    record = (await auto(client, book, payload))["transaction"]
    response = await client.post(
        BASE + f"/transactions/{record['id']}/void",
        json={"reason": "记错了"},
        headers=book["headers"],
    )
    assert response.status_code == 200, response.text
    history = (await client.get(BASE + "/transactions", headers=book["headers"])).json()["data"]
    assert history["total"] == 1 and history["items"][0]["status"] == "voided"
    response = await client.delete(BASE + f"/transactions/{record['id']}", headers=book["headers"])
    assert response.status_code == 200
    assert (await client.get(BASE + "/transactions", headers=book["headers"])).json()["data"][
        "total"
    ] == 0
    retry = await client.post(BASE + "/auto-transactions", json=payload, headers=book["headers"])
    assert retry.status_code == 409
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 0


async def test_cancelling_during_lookup_prevents_late_automatic_posting(client, book):
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_nav(*args):
        started.set()
        await release.wait()
        return 2

    with patch("app.services.automatic_trade.lookup_nav", new=slow_nav):
        task = asyncio.create_task(
            client.post(BASE + "/auto-transactions", json=request(book), headers=book["headers"])
        )
        await asyncio.wait_for(started.wait(), 3)
        # 查询清单会触发自动处理，因此只从数据库读出本用例申请编号。
        from sqlalchemy import select

        from app.db.session import async_session_factory
        from app.models.trade_application import TradeApplication

        async with async_session_factory() as session:
            row = (
                await session.execute(
                    select(TradeApplication.id).where(
                        TradeApplication.fund_id == book["fund_id"],
                        TradeApplication.status == "pending",
                    )
                )
            ).scalar_one()
        response = await client.post(BASE + f"/applications/{row}/cancel", headers=book["headers"])
        assert response.status_code == 200, response.text
        release.set()
        result = await asyncio.wait_for(task, 5)
        assert result.status_code == 409, result.text
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 0
