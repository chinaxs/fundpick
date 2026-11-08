"""记录服务端分页/筛选、撤销/作废删除权限及幂等防复活。"""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_portfolio_flow import BASE, DAY, buy, commit, portfolio
from test_portfolio_flow import book as book

from app.db.session import async_session_factory
from app.models.fund import Fund


async def application(client, book, **overrides):
    payload = {
        "code": book["code"],
        "kind": "buy",
        "amount": "100",
        "submitted_at": DAY.isoformat() + "T14:00:00+08:00",
        "pricing_rule": "auto",
        "request_key": str(uuid4()),
        **overrides,
    }
    response = await client.post(BASE + "/applications", json=payload, headers=book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"], payload


async def history(client, book, **params):
    response = await client.get(BASE + "/records", params=params, headers=book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.fixture
async def second_fund(book):
    async with async_session_factory() as session:
        while True:
            code = str(700000 + uuid4().int % 100000)
            if not (await session.execute(select(Fund.id).where(Fund.code == code))).first():
                break
        fund = Fund(code=code, name="另一只诊断%基金", type="bond")
        session.add(fund)
        await session.commit()
        fund_id = fund.id
    yield code
    # Test transactions must be removed with their member before deleting the extra fund.
    from app.models.fund_transaction import FundTransaction
    from app.models.trade_application import TradeApplication

    async with async_session_factory() as session:
        await session.execute(delete(FundTransaction).where(FundTransaction.fund_id == fund_id))
        await session.execute(delete(TradeApplication).where(TradeApplication.fund_id == fund_id))
        await session.execute(delete(Fund).where(Fund.id == fund_id))
        await session.commit()


async def test_sql_pagination_unifies_pending_cancelled_and_transactions(client, book):
    for _ in range(21):
        await commit(client, book, buy(book))
    pending, _ = await application(client, book)
    cancelled, _ = await application(client, book)
    assert (
        await client.post(BASE + f"/applications/{cancelled['id']}/cancel", headers=book["headers"])
    ).status_code == 200
    # 不能再取全量流水后在Python内分页。
    with patch(
        "app.repositories.transaction.TransactionRepository.rows",
        side_effect=AssertionError("history must use SQL page"),
    ):
        first = await history(client, book, page=1, page_size=10)
        second = await history(client, book, page=2, page_size=10)
        last = await history(client, book, page=3, page_size=10)
    assert first["total"] == second["total"] == last["total"] == 23
    assert [len(first["items"]), len(second["items"]), len(last["items"])] == [10, 10, 3]
    keys = [
        (item["record_type"], item["id"])
        for page in (first, second, last)
        for item in page["items"]
    ]
    assert len(set(keys)) == 23
    assert ("application", pending["id"]) in keys and ("application", cancelled["id"]) in keys
    pending_rows = await history(client, book, status="pending")
    assert pending_rows["total"] == 1
    assert pending_rows["items"][0]["nav"] is None and pending_rows["items"][0]["fee"] is None
    assert pending_rows["items"][0]["can_cancel"] and not pending_rows["items"][0]["can_delete"]


async def test_name_code_direction_status_date_filters_and_latest_permission(
    client, book, second_fund
):
    first, _ = await commit(client, book, buy(book))
    latest, _ = await commit(client, book, buy(book))
    await commit(client, book, buy(book, code=second_fund))
    assert (await history(client, book, keyword="交易流程"))["total"] == 2
    assert (await history(client, book, keyword=book["code"]))["total"] == 2
    assert (await history(client, book, keyword="%"))["total"] == 1
    assert (await history(client, book, keyword="_"))["total"] == 0
    assert (await history(client, book, keyword="不存在"))["total"] == 0
    assert (await history(client, book, kind="sell"))["total"] == 0
    rows = (await history(client, book, keyword=book["code"], status="confirmed", page_size=1))[
        "items"
    ]
    assert rows[0]["id"] == latest["id"] and rows[0]["can_void"]
    older = (await history(client, book, keyword=book["code"], page=2, page_size=1))["items"][0]
    assert older["id"] == first["id"] and not older["can_void"]
    _pending, _ = await application(client, book)
    assert (
        await history(client, book, status="pending", start=DAY.isoformat(), end=DAY.isoformat())
    )["total"] == 1
    assert (
        await history(client, book, status="pending", start=(DAY + timedelta(days=1)).isoformat())
    )["total"] == 0
    assert (
        await client.get(
            BASE + "/records",
            params={"start": "2026-11-06", "end": "2026-11-01"},
            headers=book["headers"],
        )
    ).status_code == 422
    assert (
        await client.get(BASE + "/records", params={"page_size": 101}, headers=book["headers"])
    ).status_code == 422
    assert (await client.get(BASE + "/records", headers=book["other"])).json()["data"]["total"] == 0


async def test_void_delete_does_not_change_portfolio_and_old_retry_cannot_recreate(client, book):
    row, confirmation = await commit(client, book, buy(book))
    path = BASE + f"/transactions/{row['id']}"
    assert (await client.delete(path, headers=book["headers"])).status_code == 409
    assert (
        await client.post(path + "/void", json={"reason": "录入错误"}, headers=book["headers"])
    ).status_code == 200
    before = (await portfolio(client, book))["summary"]
    assert (await client.delete(path, headers=book["other"])).status_code == 404
    assert (await client.delete(path, headers=book["headers"])).status_code == 200
    assert (await client.delete(path, headers=book["headers"])).status_code == 200
    assert (await history(client, book))["total"] == 0
    assert (await portfolio(client, book))["summary"] == before
    assert (
        await client.post(BASE + "/transactions", json=confirmation, headers=book["headers"])
    ).status_code == 409
    assert (
        await client.post(path + "/void", json={"reason": "再试"}, headers=book["headers"])
    ).status_code == 404


async def test_cancelled_application_visible_and_deletable_but_pending_not_deletable(client, book):
    item, request = await application(client, book)
    path = BASE + f"/applications/{item['id']}"
    assert (await client.delete(path, headers=book["headers"])).status_code == 409
    assert (await client.post(path + "/cancel", headers=book["headers"])).status_code == 200
    rows = await history(client, book, status="cancelled")
    assert rows["total"] == 1 and rows["items"][0]["can_delete"]
    assert not rows["items"][0]["can_cancel"]
    assert (await client.delete(path, headers=book["headers"])).status_code == 200
    assert (await history(client, book))["total"] == 0
    assert (
        await client.post(BASE + "/applications", json=request, headers=book["headers"])
    ).status_code == 409
    assert (await client.get(BASE + "/applications", headers=book["headers"])).json()["data"] == []


async def test_deleting_voided_latest_cannot_give_old_trade_permission(client, book):
    first, _ = await commit(client, book, buy(book))
    latest, _ = await commit(client, book, buy(book))
    assert (
        await client.post(
            BASE + f"/transactions/{latest['id']}/void",
            json={"reason": "错了"},
            headers=book["headers"],
        )
    ).status_code == 200
    await client.delete(BASE + f"/transactions/{latest['id']}", headers=book["headers"])
    rows = await history(client, book)
    assert rows["total"] == 1 and rows["items"][0]["id"] == first["id"]
    assert rows["items"][0]["can_void"]
