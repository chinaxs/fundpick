"""模拟持仓：金额录入、按买入日期自动取净值、份额折算与会员隔离。"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund import Fund
from app.models.fund_favorite import FundFavorite
from app.models.fund_nav import FundNav
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


async def _cleanup(name: str) -> None:
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
async def member(client: AsyncClient):
    name = f"tp_{uuid4().hex[:10]}"
    headers = await _register(client, name)
    yield {"username": name, "headers": headers}
    await _cleanup(name)


@pytest.fixture
async def other_member(client: AsyncClient):
    name = f"tp_{uuid4().hex[:10]}"
    headers = await _register(client, name)
    yield {"username": name, "headers": headers}
    await _cleanup(name)


async def _expected_nav(code: str, bought_at: date) -> tuple[float, date]:
    """按服务端同一口径查：买入日期当天或之前最近一个交易日净值。"""
    async with async_session_factory() as session:
        row = (
            await session.execute(
                select(FundNav.unit_nav, FundNav.nav_date)
                .join(Fund, Fund.id == FundNav.fund_id)
                .where(Fund.code == code, FundNav.nav_date <= bought_at)
                .order_by(FundNav.nav_date.desc())
                .limit(1)
            )
        ).first()
        assert row is not None, "测试基金应有历史净值"
        return float(row[0]), row[1]


async def _latest_nav() -> float:
    async with async_session_factory() as session:
        value = (
            await session.execute(select(Fund.latest_nav).where(Fund.code == "021180"))
        ).scalar_one_or_none()
        return float(value) if value is not None else 1.0


async def test_create_uses_nav_of_buy_date(client: AsyncClient, member: dict) -> None:
    """用户只填金额和日期，净值自动取、份额自动算。"""
    bought_at = date.today() - timedelta(days=30)
    nav, nav_date = await _expected_nav("021180", bought_at)

    resp = await client.post(
        BASE,
        json={
            "code": "021180",
            "amount": 10000,
            "bought_at": bought_at.isoformat(),
            "note": "模拟建仓",
        },
        headers=member["headers"],
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["cost_nav"] == round(nav, 4)
    assert item["cost_nav_date"] == nav_date.isoformat()
    assert item["nav_source"] == "history"
    assert item["shares"] == round(10000 / nav, 2)

    latest = await _latest_nav()
    assert item["market_value"] == round((10000 / nav) * latest, 2)
    assert item["profit"] == round(item["market_value"] - 10000, 2)


async def test_create_defaults_to_today(client: AsyncClient, member: dict) -> None:
    """不传日期时用今天，净值取最近一个交易日。"""
    nav, nav_date = await _expected_nav("021180", date.today())
    resp = await client.post(
        BASE,
        json={"code": "021180", "amount": 5000},
        headers=member["headers"],
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["bought_at"] == date.today().isoformat()
    assert item["cost_nav"] == round(nav, 4)
    assert item["cost_nav_date"] == nav_date.isoformat()


async def test_hand_typed_nav_is_ignored(client: AsyncClient, member: dict) -> None:
    """即使客户端传了 cost_nav，也以服务端查到的净值为准。"""
    nav, _ = await _expected_nav("021180", date.today())
    resp = await client.post(
        BASE,
        json={"code": "021180", "amount": 10000, "cost_nav": 1.0},
        headers=member["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["cost_nav"] == round(nav, 4)


async def test_fallback_to_latest_nav_when_no_history(client: AsyncClient, member: dict) -> None:
    """没有历史净值序列的基金：回退主表最新净值，并明确标注来源。"""
    async with async_session_factory() as session:
        row = (
            await session.execute(
                select(Fund.code, Fund.latest_nav).where(
                    Fund.code == "000001", Fund.latest_nav.is_not(None)
                )
            )
        ).first()
    assert row is not None, "000001 应有最新净值"

    # 显式模拟该基金无历史序列，避免用户浏览详情后补采历史导致测试前提失效。
    with patch(
        "app.repositories.position.PositionRepository.nav_on_or_before",
        new=AsyncMock(return_value=None),
    ):
        resp = await client.post(
            BASE,
            json={"code": "000001", "amount": 8000},
            headers=member["headers"],
        )
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["nav_source"] == "latest"
    assert item["cost_nav"] == round(float(row[1]), 4)
    assert item["shares"] == round(8000 / float(row[1]), 2)


async def test_edit_amount_and_date(client: AsyncClient, member: dict) -> None:
    """改金额重算份额，改日期自动换成对应日期的净值。"""
    created = await client.post(
        BASE,
        json={"code": "021180", "amount": 10000},
        headers=member["headers"],
    )
    item = created.json()["data"]
    position_id = item["id"]

    edited_amount = await client.patch(
        f"{BASE}/{position_id}",
        json={"amount": 20000},
        headers=member["headers"],
    )
    assert edited_amount.status_code == 200, edited_amount.text
    assert edited_amount.json()["data"]["shares"] == round(20000 / item["cost_nav"], 2)

    older = date.today() - timedelta(days=120)
    nav, nav_date = await _expected_nav("021180", older)
    edited_date = await client.patch(
        f"{BASE}/{position_id}",
        json={"bought_at": older.isoformat()},
        headers=member["headers"],
    )
    assert edited_date.status_code == 200, edited_date.text
    result = edited_date.json()["data"]
    assert result["cost_nav"] == round(nav, 4)
    assert result["cost_nav_date"] == nav_date.isoformat()


async def test_list_returns_items_and_summary(client: AsyncClient, member: dict) -> None:
    created = await client.post(
        BASE, json={"code": "021180", "amount": 10000}, headers=member["headers"]
    )
    position_id = created.json()["data"]["id"]

    data = (await client.get(BASE, headers=member["headers"])).json()["data"]
    assert len(data["items"]) == 1
    assert data["summary"]["count"] == 1
    assert data["summary"]["total_amount"] == 10000

    removed = await client.delete(f"{BASE}/{position_id}", headers=member["headers"])
    assert removed.status_code == 200, removed.text
    assert (await client.get(BASE, headers=member["headers"])).json()["data"]["items"] == []


async def test_position_invalid_input(client: AsyncClient, member: dict) -> None:
    assert (
        await client.post(BASE, json={"code": "021180", "amount": 0}, headers=member["headers"])
    ).status_code == 422
    assert (
        await client.post(BASE, json={"code": "999999", "amount": 100}, headers=member["headers"])
    ).status_code == 404
    assert (
        await client.post(
            BASE,
            json={
                "code": "021180",
                "amount": 100,
                "bought_at": (date.today() + timedelta(days=3)).isoformat(),
            },
            headers=member["headers"],
        )
    ).status_code in (400, 422)


async def test_position_user_isolation(
    client: AsyncClient, member: dict, other_member: dict
) -> None:
    created = await client.post(
        BASE, json={"code": "021180", "amount": 5000}, headers=member["headers"]
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
    assert (await client.get(BASE, headers=other_member["headers"])).json()["data"]["items"] == []


async def test_dashboard_only_has_position_summary(client: AsyncClient, member: dict) -> None:
    """工作台概览只带汇总，明细由独立接口提供。"""
    await client.post(
        "/api/v1/portal/favorites", json={"code": "021180"}, headers=member["headers"]
    )
    await client.post(BASE, json={"code": "021180", "amount": 12000}, headers=member["headers"])

    data = (await client.get("/api/v1/portal/me/dashboard", headers=member["headers"])).json()[
        "data"
    ]
    assert data["summary"]["total_funds"] == 1
    assert data["position_summary"]["count"] == 1
    assert data["position_summary"]["total_amount"] == 12000
    assert "favorites" not in data and "positions" not in data
