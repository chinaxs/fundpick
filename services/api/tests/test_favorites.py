"""基金关注测试。

覆盖：鉴权、增删幂等、用户隔离（A 的关注不能出现在 B 的列表里）。
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund_favorite import FundFavorite
from app.models.user import User

PASSWORD = "Portal@12345"
FUND_CODE = "002910"


async def _register(client: AsyncClient, name: str) -> tuple[str, dict[str, str]]:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def member(client: AsyncClient) -> AsyncIterator[dict[str, str]]:
    """独立会员，测试结束后连同关注记录一起清理。"""
    name = f"tf_{uuid.uuid4().hex[:10]}"
    _, headers = await _register(client, name)
    yield {"username": name, "headers": headers}

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == name))
        ).scalar_one_or_none()
        if user:
            await session.execute(delete(FundFavorite).where(FundFavorite.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def test_requires_login(client: AsyncClient) -> None:
    for method, path in (
        ("GET", "/api/v1/portal/favorites"),
        ("GET", "/api/v1/portal/favorites/codes"),
        ("POST", "/api/v1/portal/favorites"),
        ("DELETE", f"/api/v1/portal/favorites/{FUND_CODE}"),
    ):
        resp = await client.request(method, path, json={"code": FUND_CODE})
        assert resp.status_code == 401, f"{method} {path} 应要求登录"


async def test_add_list_and_remove(client: AsyncClient, member: dict) -> None:
    headers = member["headers"]

    resp = await client.post("/api/v1/portal/favorites", json={"code": FUND_CODE}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["favorited"] is True

    listed = await client.get("/api/v1/portal/favorites", headers=headers)
    assert listed.status_code == 200
    body = listed.json()["data"]
    assert body["total"] == 1
    item = body["items"][0]
    assert item["code"] == FUND_CODE
    # 列表项复用 FundListItem，带区间收益字段
    assert "return_rate" in item

    codes = await client.get("/api/v1/portal/favorites/codes", headers=headers)
    assert codes.json()["data"] == [FUND_CODE]

    removed = await client.delete(f"/api/v1/portal/favorites/{FUND_CODE}", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["data"]["favorited"] is False

    after = await client.get("/api/v1/portal/favorites", headers=headers)
    assert after.json()["data"]["total"] == 0


async def test_add_is_idempotent(client: AsyncClient, member: dict) -> None:
    headers = member["headers"]
    for _ in range(2):
        resp = await client.post(
            "/api/v1/portal/favorites", json={"code": FUND_CODE}, headers=headers
        )
        assert resp.status_code == 200

    listed = await client.get("/api/v1/portal/favorites", headers=headers)
    assert listed.json()["data"]["total"] == 1


async def test_unknown_fund_returns_404(client: AsyncClient, member: dict) -> None:
    resp = await client.post(
        "/api/v1/portal/favorites", json={"code": "000000"}, headers=member["headers"]
    )
    assert resp.status_code == 404


async def test_user_isolation(client: AsyncClient, member: dict) -> None:
    """A 关注后，B 的列表必须为空。"""
    headers_a = member["headers"]
    await client.post("/api/v1/portal/favorites", json={"code": FUND_CODE}, headers=headers_a)

    other_name = f"tf_{uuid.uuid4().hex[:10]}"
    _, headers_b = await _register(client, other_name)

    try:
        listed = await client.get("/api/v1/portal/favorites", headers=headers_b)
        assert listed.json()["data"]["total"] == 0
        codes = await client.get("/api/v1/portal/favorites/codes", headers=headers_b)
        assert codes.json()["data"] == []
    finally:
        async with async_session_factory() as session:
            user = (
                await session.execute(select(User).where(User.username == other_name))
            ).scalar_one_or_none()
            if user:
                await session.execute(delete(FundFavorite).where(FundFavorite.user_id == user.id))
                await session.execute(delete(User).where(User.id == user.id))
                await session.commit()
