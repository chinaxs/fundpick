"""买卖闭环回归：独立基金、会员隔离、并发、预览、迁移与作废。"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund import Fund
from app.models.fund_nav import FundNav
from app.models.fund_position import FundPosition
from app.models.fund_transaction import FundTransaction
from app.models.trade_application import TradeApplication
from app.models.user import User

BASE = "/api/v1/portal/me"
PASSWORD = "Portfolio@123"
DAY = date.today() - timedelta(days=20)


@pytest.fixture
async def book(client):
    names = [f"ledger_{uuid4().hex[:12]}" for _ in range(2)]
    headers = []
    for name in names:
        response = await client.post(
            "/api/v1/portal/auth/register", json={"username": name, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        headers.append({"Authorization": "Bearer " + response.json()["data"]["access_token"]})
    async with async_session_factory() as session:
        for _ in range(100):
            code = str(800000 + uuid4().int % 100000)
            if not (await session.execute(select(Fund.id).where(Fund.code == code))).first():
                break
        fund = Fund(
            code=code,
            name="交易流程测试基金",
            type="stock",
            inception_date=date(2020, 1, 1),
            latest_nav=Decimal("2.5"),
            latest_nav_date=date.today(),
        )
        session.add(fund)
        await session.flush()
        fund_id = fund.id
        session.add(FundNav(fund_id=fund_id, nav_date=DAY, unit_nav=Decimal("2")))
        await session.commit()
    yield {"headers": headers[0], "other": headers[1], "code": code, "fund_id": fund_id}
    async with async_session_factory() as session:
        users = list(
            (await session.execute(select(User.id).where(User.username.in_(names)))).scalars()
        )
        await session.execute(delete(FundTransaction).where(FundTransaction.user_id.in_(users)))
        await session.execute(delete(TradeApplication).where(TradeApplication.user_id.in_(users)))
        await session.execute(delete(FundPosition).where(FundPosition.user_id.in_(users)))
        await session.execute(delete(User).where(User.id.in_(users)))
        await session.execute(delete(FundNav).where(FundNav.fund_id == fund_id))
        await session.execute(delete(Fund).where(Fund.id == fund_id))
        await session.commit()


def buy(book, **overrides):
    return {
        "code": book["code"],
        "kind": "buy",
        "confirmed_on": DAY.isoformat(),
        "nav_mode": "manual",
        "nav": "2",
        "amount": "1010",
        "fee": "10",
        **overrides,
    }


def sell(book, **overrides):
    return {
        "code": book["code"],
        "kind": "sell",
        "confirmed_on": DAY.isoformat(),
        "nav_mode": "manual",
        "nav": "5",
        "shares": "300",
        "fee": "5",
        **overrides,
    }


async def preview(client, book, request):
    response = await client.post(
        BASE + "/transactions/preview", json=request, headers=book["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def commit(client, book, request):
    quote = await preview(client, book, request)
    body = {"request": request, "preview_hash": quote["preview_hash"], "request_key": str(uuid4())}
    response = await client.post(BASE + "/transactions", json=body, headers=book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"], body


async def portfolio(client, book):
    response = await client.get(BASE + "/portfolio", headers=book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def holding_codes(client, book, headers=None):
    response = await client.get(BASE + "/holding-codes", headers=headers or book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_buy_add_partial_sell_close_and_reopen(client, book):
    assert (await preview(client, book, buy(book)))["shares"] == 500
    assert (await portfolio(client, book))["holdings"] == []
    await commit(client, book, buy(book))
    assert await holding_codes(client, book) == [book["code"]]
    await commit(client, book, buy(book, nav="4", amount="1000", fee="0"))
    sale, _ = await commit(client, book, sell(book))
    assert sale["cash_amount"] == 1495 and sale["realized_profit"] == 691
    data = await portfolio(client, book)
    holding, summary = data["holdings"][0], data["summary"]
    assert (holding["shares"], holding["remaining_cost"], holding["market_value"]) == (
        450,
        1206,
        1125,
    )
    assert (summary["total_profit"], summary["realized_profit"], summary["total_return"]) == (
        -81,
        691,
        610,
    )
    assert (
        summary["total_return"]
        == summary["total_market_value"]
        + summary["total_sell_amount"]
        - summary["total_buy_amount"]
    )
    await commit(client, book, sell(book, shares="450", nav="3", fee="0"))
    data = await portfolio(client, book)
    assert data["summary"]["count"] == 0 and data["summary"]["total_return"] == 835
    assert data["holdings"][0]["remaining_cost"] == 0
    assert await holding_codes(client, book) == []
    await commit(client, book, buy(book))
    data = await portfolio(client, book)
    assert data["summary"]["count"] == 1 and data["summary"]["realized_profit"] == 835
    dashboard = (await client.get(BASE + "/dashboard", headers=book["headers"])).json()["data"]
    assert dashboard["portfolio_summary"] == data["summary"]


async def test_retries_stale_preview_and_concurrent_confirm(client, book):
    quote = await preview(client, book, buy(book))
    body = {
        "request": buy(book),
        "preview_hash": quote["preview_hash"],
        "request_key": str(uuid4()),
    }
    responses = await asyncio.gather(
        *[client.post(BASE + "/transactions", json=body, headers=book["headers"]) for _ in range(2)]
    )
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    assert responses[0].json()["data"]["id"] == responses[1].json()["data"]["id"]
    changed = {**body, "request": buy(book, amount="2000")}
    assert (
        await client.post(BASE + "/transactions", json=changed, headers=book["headers"])
    ).status_code == 409
    stale = await preview(client, book, buy(book))
    await commit(client, book, buy(book))
    response = await client.post(
        BASE + "/transactions",
        json={
            "request": buy(book),
            "preview_hash": stale["preview_hash"],
            "request_key": str(uuid4()),
        },
        headers=book["headers"],
    )
    assert response.status_code == 409
    assert (await portfolio(client, book))["summary"]["transaction_count"] == 2


async def test_competing_sells_cannot_oversell(client, book):
    await commit(client, book, buy(book))
    quote = await preview(client, book, sell(book))
    responses = await asyncio.gather(
        *[
            client.post(
                BASE + "/transactions",
                json={
                    "request": sell(book),
                    "preview_hash": quote["preview_hash"],
                    "request_key": str(uuid4()),
                },
                headers=book["headers"],
            )
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) in ([200, 409], [200, 422])
    assert (await portfolio(client, book))["holdings"][0]["shares"] == 200


async def test_void_and_member_isolation(client, book):
    first, _ = await commit(client, book, buy(book))
    second, _ = await commit(client, book, sell(book))
    assert await holding_codes(client, book, book["other"]) == []
    path = BASE + f"/transactions/{first['id']}/void"
    assert (
        await client.post(path, json={"reason": "测试"}, headers=book["headers"])
    ).status_code == 409
    assert (
        await client.post(path, json={"reason": "测试"}, headers=book["other"])
    ).status_code == 404
    assert (await client.get(BASE + "/portfolio", headers=book["other"])).json()["data"][
        "holdings"
    ] == []
    assert (await client.get(BASE + "/transactions", headers=book["other"])).json()["data"][
        "total"
    ] == 0
    response = await client.post(
        BASE + f"/transactions/{second['id']}/void",
        json={"reason": "录入错误"},
        headers=book["headers"],
    )
    assert response.status_code == 200 and response.json()["data"]["void_reason"] == "录入错误"
    assert (await portfolio(client, book))["holdings"][0]["shares"] == 500
    assert await holding_codes(client, book) == [book["code"]]
    history = (
        await client.get(BASE + "/transactions", headers=book["headers"], params={"page_size": 1})
    ).json()["data"]
    assert history["total"] == 2 and len(history["items"]) == 1
    assert history["items"][0]["status"] == "voided"


async def test_exact_nav_and_backdating(client, book):
    official = buy(book, nav_mode="official")
    official.pop("nav")
    assert (await preview(client, book, official))["nav"] == 2
    missing = {**official, "confirmed_on": (DAY - timedelta(days=1)).isoformat()}
    response = await client.post(
        BASE + "/transactions/preview", json=missing, headers=book["headers"]
    )
    assert response.status_code == 422 and "不会使用其他日期" in response.json()["message"]
    await commit(client, book, buy(book))
    for day in [DAY - timedelta(days=1), date.today() + timedelta(days=1)]:
        request = buy(book, confirmed_on=day.isoformat())
        assert (
            await client.post(BASE + "/transactions/preview", json=request, headers=book["headers"])
        ).status_code == 422


async def test_missing_valuation_keeps_realized_profit(client, book):
    await commit(client, book, buy(book))
    await commit(client, book, sell(book))
    async with async_session_factory() as session:
        fund = await session.get(Fund, book["fund_id"])
        fund.latest_nav_date = DAY - timedelta(days=1)
        await session.commit()
    summary = (await portfolio(client, book))["summary"]
    assert summary["valued_count"] == 0 and summary["total_market_value"] is None
    assert summary["total_return"] is None and summary["realized_profit"] == 889


async def test_legacy_review_and_undo(client, book):
    old = await client.post(
        BASE + "/positions",
        json={"code": book["code"], "amount": 1010, "bought_at": DAY.isoformat()},
        headers=book["headers"],
    )
    assert old.status_code == 200, old.text
    old_id = old.json()["data"]["id"]
    data = await portfolio(client, book)
    assert data["summary"]["legacy_count"] == 1 and data["summary"]["total_amount"] == 0
    assert await holding_codes(client, book) == []
    migration = buy(book, legacy_position_id=old_id)
    row, body = await commit(client, book, migration)
    data = await portfolio(client, book)
    assert data["summary"]["legacy_count"] == 0 and data["summary"]["total_amount"] == 1010
    assert (
        await client.post(BASE + "/transactions", json=body, headers=book["headers"])
    ).status_code == 200
    assert (
        await client.post(BASE + "/transactions/preview", json=migration, headers=book["headers"])
    ).status_code == 404
    assert (
        await client.delete(BASE + f"/positions/{old_id}", headers=book["headers"])
    ).status_code == 404
    assert (
        await client.post(
            BASE + f"/transactions/{row['id']}/void",
            json={"reason": "重新核对"},
            headers=book["headers"],
        )
    ).status_code == 200
    data = await portfolio(client, book)
    assert data["summary"]["legacy_count"] == 1 and data["holdings"] == []


@pytest.mark.parametrize("path", ["/portfolio", "/transactions", "/records", "/holding-codes"])
async def test_requires_member(client, path):
    assert (await client.get(BASE + path)).status_code == 401


async def test_invalid_inputs(client, book):
    for payload in [
        buy(book, amount="0"),
        buy(book, fee="1010"),
        buy(book, shares="1"),
        buy(book, nav="0"),
        buy(book, amount="1.001"),
        sell(book, shares="1"),
        buy(book, nav="NaN"),
        buy(book, nav="Infinity"),
    ]:
        assert (
            await client.post(BASE + "/transactions/preview", json=payload, headers=book["headers"])
        ).status_code == 422
