"""公司行为进入主账本：拆分、分红、再投、转换都要影响持仓与卖出校验。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund import Fund
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.user import User

PASSWORD = "Portal@12345"
BASE = "/api/v1/portal/me"
CODE = "000003"  # 中海可转债债券A
PAIR = "000004"  # 同基金 C 类，用于转换


@pytest.fixture
async def member(client: AsyncClient) -> AsyncIterator[dict]:
    name = f"ev_{uuid.uuid4().hex[:10]}"
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "email": f"{name}@qq.com", "password": PASSWORD},
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
    yield {"username": name, "id": user_id, "headers": headers}

    async with async_session_factory() as session:
        if user_id:
            await session.execute(delete(FundTransaction).where(FundTransaction.user_id == user_id))
            await session.execute(
                delete(FundPortfolioFlow).where(FundPortfolioFlow.user_id == user_id)
            )
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def _import_buy(
    client: AsyncClient, headers: dict, *, shares: str, amount: str, nav: str, days_ago: int = 30
) -> None:
    resp = await client.post(
        f"{BASE}/portfolio/import",
        json={
            "rows": [
                {
                    "code": CODE,
                    "confirmed_on": (date.today() - timedelta(days=days_ago)).isoformat(),
                    "shares": shares,
                    "amount": amount,
                    "nav": nav,
                    "platform": "支付宝",
                }
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["created"] == 1


async def _add_flow(client: AsyncClient, headers: dict, payload: dict) -> dict:
    resp = await client.post(f"{BASE}/portfolio/flows", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _holdings(client: AsyncClient, headers: dict) -> dict:
    resp = await client.get(f"{BASE}/portfolio", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _sell(client: AsyncClient, headers: dict, *, shares: str, nav: str) -> dict:
    request = {
        "code": CODE,
        "kind": "sell",
        "confirmed_on": date.today().isoformat(),
        "nav_mode": "manual",
        "nav": nav,
        "shares": shares,
        "fee": "0",
    }
    preview = await client.post(f"{BASE}/transactions/preview", json=request, headers=headers)
    return {"request": request, "preview": preview}


async def test_split_updates_position_and_allows_selling_new_shares(
    client: AsyncClient, member: dict
) -> None:
    await _import_buy(client, member["headers"], shares="500", amount="600", nav="1.2")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "split",
            "effective_on": (date.today() - timedelta(days=20)).isoformat(),
            "ratio": "2",
        },
    )

    holding = (await _holdings(client, member["headers"]))["holdings"][0]
    assert holding["shares"] == 1000.0
    # 拆分不改变总成本，只是每股成本减半
    assert holding["remaining_cost"] == 600.0
    assert holding["average_cost"] == pytest.approx(0.6)

    preview = await _sell(client, member["headers"], shares="800", nav="1.3")
    assert preview["preview"].status_code == 200, preview["preview"].text
    body = preview["preview"].json()["data"]
    assert body["remaining_shares"] == 200.0
    # 1040 回款 - 600×0.8 成本 = 560
    assert body["realized_profit"] == pytest.approx(560.0, rel=0.01)

    confirm = await client.post(
        f"{BASE}/transactions",
        json={
            "request": preview["request"],
            "preview_hash": body["preview_hash"],
            "request_key": str(uuid.uuid4()),
        },
        headers=member["headers"],
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["data"]["status"] == "confirmed"

    holding = (await _holdings(client, member["headers"]))["holdings"][0]
    assert holding["shares"] == 200.0
    assert holding["remaining_cost"] == 120.0


async def test_reinvest_adds_shares_and_cost(client: AsyncClient, member: dict) -> None:
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "reinvest",
            "effective_on": (date.today() - timedelta(days=10)).isoformat(),
            "shares_delta": "30",
            "nav": "1.2",
        },
    )
    holding = (await _holdings(client, member["headers"]))["holdings"][0]
    assert holding["shares"] == 1030.0
    assert holding["remaining_cost"] == pytest.approx(1236.0)


async def test_dividend_counts_in_total_return(client: AsyncClient, member: dict) -> None:
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "dividend",
            "effective_on": (date.today() - timedelta(days=5)).isoformat(),
            "cash_amount": "36.50",
        },
    )
    data = await _holdings(client, member["headers"])
    holding = data["holdings"][0]
    assert holding["dividends"] == 36.5
    assert holding["realized_profit"] == 36.5
    assert data["summary"]["total_dividends"] == 36.5


async def test_conversion_writes_paired_rows_and_transfers_cost(
    client: AsyncClient, member: dict
) -> None:
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    created = await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=3)).isoformat(),
            "shares_delta": "-500",
            "nav": "1.2",
            "target_code": PAIR,
            # 转入份额按回执填写：服务端不再复制转出份额
            "target_shares": "500",
            "target_nav": "1.2",
        },
    )
    assert created["kind"] == "convert_out"

    flows = (await client.get(f"{BASE}/portfolio/flows", headers=member["headers"])).json()["data"]
    assert len(flows) == 2
    kinds = {flow["kind"] for flow in flows}
    assert kinds == {"convert_out", "convert_in"}
    out = next(flow for flow in flows if flow["kind"] == "convert_out")
    into = next(flow for flow in flows if flow["kind"] == "convert_in")
    assert out["target_code"] == PAIR
    assert into["code"] == PAIR
    assert out["shares_delta"] == -500.0
    assert into["shares_delta"] == 500.0
    # 转出成本按先进先出结转：600 元
    assert into["cash_amount"] == pytest.approx(600.0)

    portfolios = (await _holdings(client, member["headers"]))["holdings"]
    by_code = {item["code"]: item for item in portfolios}
    assert by_code[CODE]["shares"] == 500.0
    assert by_code[CODE]["remaining_cost"] == pytest.approx(600.0)
    assert by_code[PAIR]["shares"] == 500.0
    assert by_code[PAIR]["remaining_cost"] == pytest.approx(600.0)

    # 删除任一条，整组一起消失，避免留下单边份额
    removed = await client.delete(f"{BASE}/portfolio/flows/{out['id']}", headers=member["headers"])
    assert removed.status_code == 200
    remaining = (await client.get(f"{BASE}/portfolio/flows", headers=member["headers"])).json()[
        "data"
    ]
    assert remaining == []


async def test_conversion_requires_available_shares(client: AsyncClient, member: dict) -> None:
    await _import_buy(client, member["headers"], shares="100", amount="120", nav="1.2")
    resp = await client.post(
        f"{BASE}/portfolio/flows",
        json={
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=1)).isoformat(),
            "shares_delta": "-500",
            "target_code": PAIR,
        },
        headers=member["headers"],
    )
    assert resp.status_code in (400, 422), resp.text


async def test_reconciliation_uses_replayed_shares(client: AsyncClient, member: dict) -> None:
    await _import_buy(client, member["headers"], shares="500", amount="600", nav="1.2")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "split",
            "effective_on": (date.today() - timedelta(days=20)).isoformat(),
            "ratio": "2",
        },
    )
    data = (await client.get(f"{BASE}/portfolio/reconciliation", headers=member["headers"])).json()[
        "data"
    ]
    fund = next(item for item in data["funds"] if item["code"] == CODE)
    assert fund["ledger_shares"] == 500.0
    assert fund["flow_shares_delta"] == 500.0
    assert fund["expected_shares"] == 1000.0
    assert Decimal(str(data["invested"])) == Decimal("600")


async def test_reinvest_records_platform_and_keeps_total_return(
    client: AsyncClient, member: dict
) -> None:
    """再投只落在一个平台，且红利计入总收益（不能只加成本不加收益）。"""
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    created = await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "reinvest",
            "effective_on": (date.today() - timedelta(days=10)).isoformat(),
            "shares_delta": "30",
            "nav": "1.2",
        },
    )
    assert created["platform"] == "支付宝"

    data = await _holdings(client, member["headers"])
    summary = data["summary"]
    expected = (
        summary["total_market_value"] + summary["total_sell_amount"] - summary["total_buy_amount"]
    )
    assert summary["total_return"] == pytest.approx(expected, rel=0.001)


async def test_conversion_keeps_actual_target_shares(client: AsyncClient, member: dict) -> None:
    """转换两侧净值不同时，转入份额必须按实际确认值记录，不能复制转出份额。"""
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=3)).isoformat(),
            "shares_delta": "-500",
            "nav": "1.2",
            "cash_amount": "600",
            "target_code": PAIR,
            "target_shares": "1200",
            "target_nav": "0.5",
        },
    )
    portfolios = (await _holdings(client, member["headers"]))["holdings"]
    by_code = {item["code"]: item for item in portfolios}
    assert by_code[PAIR]["shares"] == 1200.0
    # 转入成本按结转金额计，不按份额复制
    assert by_code[PAIR]["remaining_cost"] == pytest.approx(600.0)


async def test_flow_request_key_is_idempotent(client: AsyncClient, member: dict) -> None:
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    payload = {
        "code": CODE,
        "kind": "dividend",
        "effective_on": (date.today() - timedelta(days=4)).isoformat(),
        "cash_amount": "12.00",
        "request_key": f"dividend-{uuid.uuid4().hex[:8]}",
    }
    first = await _add_flow(client, member["headers"], payload)
    second = await _add_flow(client, member["headers"], payload)
    assert first["id"] == second["id"]
    flows = (await client.get(f"{BASE}/portfolio/flows", headers=member["headers"])).json()["data"]
    assert len(flows) == 1


async def test_multi_platform_flow_requires_platform(client: AsyncClient, member: dict) -> None:
    """多平台持有且未指定归属时必须拒绝：不能按份额最大去猜真实平台。"""
    fund_id = (await _holdings(client, member["headers"]))["holdings"]
    assert fund_id == []
    async with async_session_factory() as session:
        fund = (await session.execute(select(Fund).where(Fund.code == CODE))).scalar_one_or_none()
        assert fund is not None
        for platform, shares in (("A", "100"), ("B", "200")):
            session.add(
                FundTransaction(
                    user_id=member["id"],
                    fund_id=fund.id,
                    kind="buy",
                    status="confirmed",
                    confirmed_on=date.today() - timedelta(days=30),
                    nav=Decimal("1"),
                    nav_source="manual",
                    amount=Decimal(shares),
                    fee=Decimal("0"),
                    shares=Decimal(shares),
                    cash_amount=Decimal(shares),
                    realized_profit=Decimal("0"),
                    remaining_shares=Decimal(shares),
                    remaining_cost=Decimal(shares),
                    platform=platform,
                    record_source="estimated",
                    request_key=str(uuid.uuid4()),
                    request_hash="x" * 64,
                )
            )
        await session.commit()

    resp = await client.post(
        f"{BASE}/portfolio/flows",
        json={
            "code": CODE,
            "kind": "dividend",
            "effective_on": (date.today() - timedelta(days=5)).isoformat(),
            "cash_amount": "10",
        },
        headers=member["headers"],
    )
    assert resp.status_code == 422
    assert "平台" in resp.json()["message"]


async def test_conversion_requires_target_quantity(client: AsyncClient, member: dict) -> None:
    """只给转出份额、不给目标侧数据时必须拒绝，不能编造已入账份额。"""
    await _import_buy(client, member["headers"], shares="1000", amount="1200", nav="1.2")
    resp = await client.post(
        f"{BASE}/portfolio/flows",
        json={
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=3)).isoformat(),
            "shares_delta": "-500",
            "target_code": PAIR,
        },
        headers=member["headers"],
    )
    assert resp.status_code == 422
    # 单边写入必须回滚：转出侧不能留下一条
    flows = (await client.get(f"{BASE}/portfolio/flows", headers=member["headers"])).json()["data"]
    assert flows == []


async def test_backdated_flow_cannot_break_later_sale(client: AsyncClient, member: dict) -> None:
    """补录过去的转出不能让之后已成交的卖出变成负份额。"""
    await _import_buy(client, member["headers"], shares="100", amount="100", nav="1")
    commit_resp = await client.post(
        f"{BASE}/transactions",
        json={
            "request": {
                "code": CODE,
                "kind": "sell",
                "confirmed_on": (date.today() - timedelta(days=3)).isoformat(),
                "nav_mode": "manual",
                "nav": "1",
                "shares": "80",
                "fee": "0",
            },
            **{
                "preview_hash": (
                    await client.post(
                        f"{BASE}/transactions/preview",
                        json={
                            "code": CODE,
                            "kind": "sell",
                            "confirmed_on": (date.today() - timedelta(days=3)).isoformat(),
                            "nav_mode": "manual",
                            "nav": "1",
                            "shares": "80",
                            "fee": "0",
                        },
                        headers=member["headers"],
                    )
                ).json()["data"]["preview_hash"],
            },
            "request_key": str(uuid.uuid4()),
        },
        headers=member["headers"],
    )
    assert commit_resp.status_code == 200, commit_resp.text

    resp = await client.post(
        f"{BASE}/portfolio/flows",
        json={
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=5)).isoformat(),
            "shares_delta": "-80",
            "target_code": PAIR,
            "target_shares": "80",
            "target_nav": "1",
        },
        headers=member["headers"],
    )
    assert resp.status_code in (409, 422)
    holdings = (await _holdings(client, member["headers"]))["holdings"]
    assert all(item["shares"] >= 0 for item in holdings)


async def test_conversion_loss_counts_as_realized(client: AsyncClient, member: dict) -> None:
    """转出 120、目标只到账 108：12 元转换费用必须进收益，不能凭空消失。"""
    await _import_buy(client, member["headers"], shares="100", amount="120", nav="1.2")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=3)).isoformat(),
            "shares_delta": "-100",
            "nav": "1.2",
            "cash_amount": "120",
            "target_code": PAIR,
            "target_shares": "90",
            "target_nav": "1.2",
        },
    )
    data = await _holdings(client, member["headers"])
    summary = data["summary"]
    expected = (
        summary["total_market_value"] + summary["total_sell_amount"] - summary["total_buy_amount"]
    )
    # 总收益与"市值 + 卖出 - 买入"必须一致：转换损耗不能从账上消失
    assert summary["total_return"] == pytest.approx(expected)
    # 已实现部分就是 120 转出、108 到账的差额（与后来净值波动无关）
    out = next(item for item in data["holdings"] if item["code"] == CODE)
    assert out["realized_profit"] == pytest.approx(-12.0)


async def test_backdated_sell_cannot_break_later_conversion(
    client: AsyncClient, member: dict
) -> None:
    """补录一笔过去的卖出，不能把之后已记录的转换变成负份额。"""
    await _import_buy(client, member["headers"], shares="100", amount="100", nav="1")
    await _add_flow(
        client,
        member["headers"],
        {
            "code": CODE,
            "kind": "convert_out",
            "effective_on": (date.today() - timedelta(days=2)).isoformat(),
            "shares_delta": "-80",
            "cash_amount": "80",
            "target_code": PAIR,
            "target_shares": "80",
            "target_nav": "1",
        },
    )
    resp = await client.post(
        f"{BASE}/transactions/preview",
        json={
            "code": CODE,
            "kind": "sell",
            "confirmed_on": (date.today() - timedelta(days=4)).isoformat(),
            "nav_mode": "manual",
            "nav": "1",
            "shares": "80",
            "fee": "0",
        },
        headers=member["headers"],
    )
    assert resp.status_code in (409, 422)
    holdings = (await _holdings(client, member["headers"]))["holdings"]
    assert all(item["shares"] >= 0 for item in holdings)
