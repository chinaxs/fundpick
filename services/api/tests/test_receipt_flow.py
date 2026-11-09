"""平台回执精度、申请时间与待确认生命周期。"""

from uuid import uuid4

from test_portfolio_flow import BASE, buy, commit, holding_codes, portfolio, preview, sell
from test_portfolio_flow import book as book


def receipt(book, **overrides):
    return {
        **buy(book),
        "confirmed_on": "2026-11-06",
        "record_source": "receipt",
        "submitted_at": "2026-11-06T14:59:59+08:00",
        "settled_on": "2026-11-06",
        "platform": "平台A",
        "pricing_rule": "cn_open",
        "confirmed_shares": "499.99",
        **overrides,
    }


async def test_receipt_exact_shares_and_platform_separation(client, book):
    record, _ = await commit(client, book, receipt(book))
    assert record["shares"] == 499.99
    assert record["submitted_at"] == "2026-11-06T14:59:59+08:00"
    assert record["settled_on"] == "2026-11-06"
    assert record["record_source"] == "receipt"
    await commit(client, book, receipt(book, platform="平台B", nav="4", confirmed_shares="250"))
    sale = sell(
        book,
        record_source="receipt",
        confirmed_on="2026-11-06",
        submitted_at="2026-11-06T14:59:59+08:00",
        settled_on="2026-11-06",
        platform="平台A",
        pricing_rule="cn_open",
        shares="100",
        received_amount="494.99",
    )
    row, _ = await commit(client, book, sale)
    assert row["cash_amount"] == 494.99
    assert row["realized_profit"] == 292.99
    data = await portfolio(client, book)
    assert data["holdings"][0]["shares"] == 649.99
    assert data["holdings"][0]["remaining_cost"] == 1818
    oversell = {**sale, "platform": "平台B", "shares": "300"}
    assert (
        await client.post(BASE + "/transactions/preview", json=oversell, headers=book["headers"])
    ).status_code == 422

    # 清空平台B后，平台A仍有持仓，基金标识不能随最后一笔快照消失。
    await commit(
        client, book, {**sale, "platform": "平台B", "shares": "250", "received_amount": "1245"}
    )
    assert await holding_codes(client, book) == [book["code"]]


async def test_cutoff_is_enforced_and_platform_exception_is_explicit(client, book):
    wrong = receipt(book, submitted_at="2026-11-05T15:00:00+08:00")
    assert (await preview(client, book, wrong))["confirmed_on"] == "2026-11-06"
    wrong["submitted_at"] = "2026-11-06T15:00:00+08:00"
    response = await client.post(
        BASE + "/transactions/preview", json=wrong, headers=book["headers"]
    )
    assert response.status_code == 422 and "2026-11-09" in response.json()["message"]
    timing = await client.post(
        BASE + "/transactions/timing",
        json={"code": book["code"], "submitted_at": "2026-09-30T15:00:00+08:00"},
        headers=book["headers"],
    )
    assert timing.status_code == 200 and timing.json()["data"]["expected_nav_on"] == "2026-10-08"
    special = receipt(book, pricing_rule="platform", confirmed_on="2026-11-06")
    assert (
        await client.post(BASE + "/transactions/preview", json=special, headers=book["headers"])
    ).status_code == 422
    special["date_reason"] = "按平台回执"
    assert (await preview(client, book, special))["confirmed_on"] == "2026-11-06"


async def test_pending_application_does_not_create_holdings_and_can_record_receipt(client, book):
    application = {
        "code": book["code"],
        "kind": "buy",
        "platform": "平台A",
        "amount": "1010",
        "submitted_at": "2026-11-06T14:59:59+08:00",
        "pricing_rule": "cn_open",
        "request_key": str(uuid4()),
    }
    response = await client.post(BASE + "/applications", json=application, headers=book["headers"])
    assert response.status_code == 200, response.text
    application_id = response.json()["data"]["id"]
    retry = await client.post(BASE + "/applications", json=application, headers=book["headers"])
    assert retry.json()["data"]["id"] == application_id
    assert (await portfolio(client, book))["holdings"] == []
    assert await holding_codes(client, book) == []
    assert (await client.get(BASE + "/applications", headers=book["other"])).json()["data"] == []
    assert (
        await client.post(BASE + f"/applications/{application_id}/cancel", headers=book["other"])
    ).status_code == 404
    await commit(client, book, receipt(book, application_id=application_id))
    assert (await client.get(BASE + "/applications", headers=book["headers"])).json()["data"] == []
    assert (await portfolio(client, book))["holdings"][0]["shares"] == 499.99
    assert (
        await client.post(
            BASE + "/transactions/preview",
            json=receipt(book, application_id=application_id),
            headers=book["headers"],
        )
    ).status_code == 409


async def test_receipt_requires_actual_values(client, book):
    for key in (
        "confirmed_shares",
        "submitted_at",
        "platform",
        "pricing_rule",
        "fee",
    ):
        request = receipt(book)
        request.pop(key)
        assert (
            await client.post(BASE + "/transactions/preview", json=request, headers=book["headers"])
        ).status_code == 422
    request = receipt(book, submitted_at="2026-11-06T14:59:59")
    assert (
        await client.post(BASE + "/transactions/preview", json=request, headers=book["headers"])
    ).status_code == 422


async def test_simple_record_requires_only_fund_money_and_time(client, book):
    request = {
        "code": book["code"],
        "kind": "buy",
        "amount": "1000",
        "submitted_at": "2026-11-06T15:00:00+08:00",
        "pricing_rule": "auto",
        "request_key": str(uuid4()),
    }
    response = await client.post(BASE + "/applications", json=request, headers=book["headers"])
    assert response.status_code == 200, response.text
    item = response.json()["data"]
    assert item["platform"] == ""
    assert item["expected_nav_on"] == "2026-11-09"
    assert (await portfolio(client, book))["holdings"] == []
    assert (
        await client.post(BASE + "/applications", json=request, headers=book["headers"])
    ).json()["data"]["id"] == item["id"]


async def test_fill_receipt_can_add_missing_platform_and_leave_confirmation_date_unknown(
    client, book
):
    request = {
        "code": book["code"],
        "kind": "buy",
        "amount": "1010",
        "submitted_at": "2026-11-06T14:59:59+08:00",
        "pricing_rule": "auto",
        "request_key": str(uuid4()),
    }
    item = (
        await client.post(BASE + "/applications", json=request, headers=book["headers"])
    ).json()["data"]
    result = receipt(book, application_id=item["id"])
    result.pop("settled_on")
    record, _ = await commit(client, book, result)
    assert record["platform"] == "平台A"
    assert record["settled_on"] is None
    assert record["shares"] == 499.99
    assert (await client.get(BASE + "/applications", headers=book["headers"])).json()["data"] == []


async def test_auto_calendar_keeps_special_products_and_unknown_year_pending(client, book):
    from app.db.session import async_session_factory
    from app.models.fund import Fund

    async with async_session_factory() as session:
        fund = await session.get(Fund, book["fund_id"])
        fund.type = "qdii"
        await session.commit()
    request = {
        "code": book["code"],
        "submitted_at": "2026-11-06T14:00:00+08:00",
        "pricing_rule": "auto",
    }
    response = await client.post(
        BASE + "/transactions/timing", json=request, headers=book["headers"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["expected_nav_on"] is None
    assert response.json()["data"]["pricing_rule"] == "platform"
    pending = {**request, "kind": "buy", "amount": "1000", "request_key": str(uuid4())}
    response = await client.post(BASE + "/applications", json=pending, headers=book["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["expected_nav_on"] is None
    request["submitted_at"] = "2024-11-06T14:00:00+08:00"
    assert (
        await client.post(BASE + "/transactions/timing", json=request, headers=book["headers"])
    ).json()["data"]["expected_nav_on"] is None
