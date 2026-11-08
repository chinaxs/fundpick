"""持仓工具：历史导入、公司行为流水、收益核对与导出。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.user import User

PASSWORD = "Portal@12345"
BASE = "/api/v1/portal/me/portfolio"
CODE = "000003"  # 中海可转债债券A


@pytest.fixture
async def member(client: AsyncClient) -> AsyncIterator[dict]:
    name = f"pt_{uuid.uuid4().hex[:10]}"
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "email": f"{name}@qq.com", "password": PASSWORD},
    )
    token = resp.json()["data"]["access_token"]
    yield {"username": name, "headers": {"Authorization": f"Bearer {token}"}}

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        if user_id:
            await session.execute(delete(FundTransaction).where(FundTransaction.user_id == user_id))
            await session.execute(
                delete(FundPortfolioFlow).where(FundPortfolioFlow.user_id == user_id)
            )
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


def _row(**overrides) -> dict:
    payload = {
        "code": CODE,
        "confirmed_on": (date.today() - timedelta(days=30)).isoformat(),
        "shares": "1000",
        "amount": "1200",
        "nav": "1.2",
    }
    payload.update(overrides)
    return payload


async def test_import_requires_login(client: AsyncClient) -> None:
    assert (await client.post(f"{BASE}/import", json={"rows": [_row()]})).status_code == 401


async def test_import_dry_run_does_not_write(client: AsyncClient, member: dict) -> None:
    resp = await client.post(
        f"{BASE}/import", json={"rows": [_row()], "dry_run": True}, headers=member["headers"]
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["dry_run"] is True
    assert data["created"] == 0
    assert data["imported"][0]["code"] == CODE

    holdings = await client.get("/api/v1/portal/me/portfolio", headers=member["headers"])
    assert holdings.json()["data"]["holdings"] == []


async def test_import_creates_ledger_positions(client: AsyncClient, member: dict) -> None:
    older = _row(confirmed_on=(date.today() - timedelta(days=60)).isoformat())
    newer = _row(
        confirmed_on=(date.today() - timedelta(days=10)).isoformat(),
        shares="500",
        nav="1.5",
        amount=None,
    )
    resp = await client.post(
        f"{BASE}/import", json={"rows": [older, newer]}, headers=member["headers"]
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 2
    assert not data["errors"]

    portfolio = await client.get("/api/v1/portal/me/portfolio", headers=member["headers"])
    holdings = portfolio.json()["data"]["holdings"]
    holding = next(item for item in holdings if item["code"] == CODE)
    assert holding["shares"] == 1500.0
    # 第二笔按 500 × 1.5 推算金额
    assert holding["remaining_cost"] == pytest.approx(1950.0, rel=0.01)


async def test_import_rejects_fund_with_existing_records(client: AsyncClient, member: dict) -> None:
    first = await client.post(f"{BASE}/import", json={"rows": [_row()]}, headers=member["headers"])
    assert first.status_code == 200

    second = await client.post(f"{BASE}/import", json={"rows": [_row()]}, headers=member["headers"])
    assert second.status_code == 200, second.text
    data = second.json()["data"]
    assert data["created"] == 0
    assert "已有交易记录" in data["errors"][0]["reason"]


async def test_import_reports_invalid_rows(client: AsyncClient, member: dict) -> None:
    resp = await client.post(
        f"{BASE}/import",
        json={
            "rows": [
                _row(code="999999"),
                {"code": CODE, "confirmed_on": date.today().isoformat(), "shares": "1"},
            ]
        },
        headers=member["headers"],
    )
    assert resp.status_code == 422  # 第二行缺两项数字，schema 层就拒
    detail = resp.json()["data"]
    assert detail


async def test_flow_create_validation(client: AsyncClient, member: dict) -> None:
    missing_amount = await client.post(
        f"{BASE}/flows",
        json={"code": CODE, "kind": "dividend", "effective_on": date.today().isoformat()},
        headers=member["headers"],
    )
    assert missing_amount.status_code == 422

    convert_without_target = await client.post(
        f"{BASE}/flows",
        json={
            "code": CODE,
            "kind": "convert_in",
            "effective_on": date.today().isoformat(),
            "shares_delta": "10",
        },
        headers=member["headers"],
    )
    assert convert_without_target.status_code == 422


async def test_flows_and_reconciliation(client: AsyncClient, member: dict) -> None:
    await client.post(f"{BASE}/import", json={"rows": [_row()]}, headers=member["headers"])

    dividend = await client.post(
        f"{BASE}/flows",
        json={
            "code": CODE,
            "kind": "dividend",
            "effective_on": (date.today() - timedelta(days=20)).isoformat(),
            "cash_amount": "36.50",
            "note": "每份派 0.0365",
        },
        headers=member["headers"],
    )
    assert dividend.status_code == 201, dividend.text

    reinvest = await client.post(
        f"{BASE}/flows",
        json={
            "code": CODE,
            "kind": "reinvest",
            "effective_on": (date.today() - timedelta(days=19)).isoformat(),
            "shares_delta": "30",
            # 再投必须给出金额或净值：不允许拿原持仓平均成本猜这笔红利
            "nav": "1",
        },
        headers=member["headers"],
    )
    assert reinvest.status_code == 201

    flows = await client.get(f"{BASE}/flows", headers=member["headers"])
    assert len(flows.json()["data"]) == 2
    assert {item["kind"] for item in flows.json()["data"]} == {"dividend", "reinvest"}

    result = (await client.get(f"{BASE}/reconciliation", headers=member["headers"])).json()["data"]
    fund = next(item for item in result["funds"] if item["code"] == CODE)
    assert fund["ledger_shares"] == 1000.0
    assert fund["flow_shares_delta"] == 30.0
    assert fund["expected_shares"] == 1030.0
    assert result["dividends"] == 36.5
    assert result["invested"] == 1200.0
    assert "不自动改写" in result["note"]

    flow_id = flows.json()["data"][0]["id"]
    removed = await client.delete(f"{BASE}/flows/{flow_id}", headers=member["headers"])
    assert removed.status_code == 200
    remaining = await client.get(f"{BASE}/flows", headers=member["headers"])
    assert len(remaining.json()["data"]) == 1


async def test_export_csv(client: AsyncClient, member: dict) -> None:
    await client.post(f"{BASE}/import", json={"rows": [_row()]}, headers=member["headers"])
    resp = await client.get(f"{BASE}/export", headers=member["headers"])
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.content.decode("utf-8-sig")
    assert "基金代码" in body
    assert CODE in body
    assert "buy" in body


async def test_flows_are_isolated_between_members(client: AsyncClient, member: dict) -> None:
    await client.post(f"{BASE}/import", json={"rows": [_row()]}, headers=member["headers"])
    created = await client.post(
        f"{BASE}/flows",
        json={
            "code": CODE,
            "kind": "split",
            "effective_on": date.today().isoformat(),
            "ratio": "2",
            "shares_delta": "1000",
        },
        headers=member["headers"],
    )
    flow_id = created.json()["data"]["id"]

    other_name = f"po_{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": other_name, "email": f"{other_name}@qq.com", "password": PASSWORD},
    )
    other = {"Authorization": f"Bearer {reg.json()['data']['access_token']}"}

    assert (await client.get(f"{BASE}/flows", headers=other)).json()["data"] == []
    denied = await client.delete(f"{BASE}/flows/{flow_id}", headers=other)
    assert denied.status_code == 404

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == other_name))
        if user_id:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
