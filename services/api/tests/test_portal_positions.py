"""模拟持仓：金额录入、份额折算、盈亏计算与会员隔离。"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund import Fund
from app.models.fund_favorite import FundFavorite
from app.models.fund_position import FundPosition
from app.models.user import User

PASSWORD = "Portal@12345"
BASE = "/api/v1/portal/me/positions"


async def _register(client: AsyncClient, name: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture
async def member(client: AsyncClient):
    name = f"tp_{uuid4().hex[:10]}"
    headers = await _register(client, name)
    yield {"username": name, "headers": headers}

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == name))
        ).scalar_one_or_none()
        if user:
            await session.execute(delete(FundPosition).where(FundPosition.user_id == user.id))
            await session.execute(delete(FundFavorite).where(FundFavorite.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


@pytest.fixture
async def other_member(client: AsyncClient):
    name = f"tp_{uuid4().hex[:10]}"
    headers = await _register(client, name)
    yield {"username": name, "headers": headers}

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == name))
        ).scalar_one_or_none()
        if user:
            await session.execute(delete(FundPosition).where(FundPosition.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def _latest_nav() -> float:
    async with async_session_factory() as session:
        value = (
            await session.execute(select(Fund.latest_nav).where(Fund.code == "021180"))
        ).scalar_one_or_none()
        return float(value) if value is not None else 1.0


async def test_position_crud_and_shares(client: AsyncClient, member: dict) -> None:
    """只录金额：份额 = 金额 / 买入净值，市值/盈亏按最新净值算。"""
    nav = await _latest_nav()
    resp = await client.post(
        BASE,
        json={"code": "021180", "amount": 10000, "cost_nav": 1.25, "note": "模拟建仓"},
        headers=member["headers"],
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["amount"] == 10000
    assert item["shares"] == 8000.0, "10000 / 1.25 = 8000 份"
    assert item["latest_nav"] == round(nav, 4)
    expected_value = round(8000 * nav, 2)
    assert item["market_value"] == expected_value
    assert item["profit"] == round(expected_value - 10000, 2)
    assert item["profit_rate"] == round((expected_value - 10000) / 10000 * 100, 2)

    position_id = item["id"]

    # 编辑金额后份额自动重算
    edited = await client.patch(
        f"{BASE}/{position_id}",
        json={"amount": 20000},
        headers=member["headers"],
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["shares"] == 16000.0
    assert edited.json()["data"]["cost_nav"] == 1.25, "未提供的字段保持原值"

    listed = await client.get(BASE, headers=member["headers"])
    assert len(listed.json()["data"]) == 1

    removed = await client.delete(f"{BASE}/{position_id}", headers=member["headers"])
    assert removed.status_code == 200, removed.text
    assert (await client.get(BASE, headers=member["headers"])).json()["data"] == []


async def test_position_invalid_input(client: AsyncClient, member: dict) -> None:
    assert (
        await client.post(
            BASE,
            json={"code": "021180", "amount": 0, "cost_nav": 1.25},
            headers=member["headers"],
        )
    ).status_code == 422
    assert (
        await client.post(
            BASE,
            json={"code": "999999", "amount": 100, "cost_nav": 1.25},
            headers=member["headers"],
        )
    ).status_code == 404


async def test_position_user_isolation(
    client: AsyncClient, member: dict, other_member: dict
) -> None:
    """不能编辑/删除别人的持仓，也不能在对方列表里看到。"""
    created = await client.post(
        BASE,
        json={"code": "021180", "amount": 5000, "cost_nav": 1.0},
        headers=member["headers"],
    )
    position_id = created.json()["data"]["id"]

    assert (
        await client.patch(
            f"{BASE}/{position_id}",
            json={"amount": 1},
            headers=other_member["headers"],
        )
    ).status_code == 404
    assert (
        await client.delete(f"{BASE}/{position_id}", headers=other_member["headers"])
    ).status_code == 404
    assert (await client.get(BASE, headers=other_member["headers"])).json()["data"] == []


async def test_dashboard_includes_favorites_and_positions(
    client: AsyncClient, member: dict
) -> None:
    """工作台带完整收藏列表与持仓汇总。"""
    await client.post(
        "/api/v1/portal/favorites", json={"code": "021180"}, headers=member["headers"]
    )
    nav = await _latest_nav()
    await client.post(
        BASE,
        json={"code": "021180", "amount": 12000, "cost_nav": 1.2},
        headers=member["headers"],
    )

    data = (
        await client.get("/api/v1/portal/me/dashboard", headers=member["headers"])
    ).json()["data"]
    assert [f["code"] for f in data["favorites"]] == ["021180"]
    assert len(data["positions"]) == 1
    summary = data["position_summary"]
    assert summary["count"] == 1
    assert summary["total_amount"] == 12000
    assert summary["total_market_value"] == round(10000 * nav, 2)
    assert summary["total_profit"] == round(10000 * nav - 12000, 2)
