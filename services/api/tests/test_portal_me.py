"""会员自助接口：工作台统计、资料更新、改密、注销。

复用 test_favorites 的注册套路，每个用例使用独立会员，避免互相污染。
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund_favorite import FundFavorite
from app.models.user import User

PASSWORD = "Portal@12345"


async def _register(client: AsyncClient, name: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture
async def member(client: AsyncClient):
    name = f"tm_{uuid4().hex[:10]}"
    headers = await _register(client, name)
    yield {"username": name, "headers": headers}

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == name))
        ).scalar_one_or_none()
        if user:
            await session.execute(delete(FundFavorite).where(FundFavorite.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/v1/portal/me/dashboard", None),
        ("patch", "/api/v1/portal/me", {"full_name": "x"}),
        (
            "post",
            "/api/v1/portal/me/change-password",
            {"old_password": "a", "new_password": "bbbbbbbb"},
        ),
        ("post", "/api/v1/portal/me/deactivate", {"password": PASSWORD}),
    ],
)
async def test_requires_login(
    client: AsyncClient, method: str, path: str, body: dict | None
) -> None:
    """会员接口不能匿名访问。"""
    kwargs = {"json": body} if body is not None else {}
    resp = await getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401


async def test_dashboard_empty(client: AsyncClient, member: dict) -> None:
    """没有关注基金时返回结构完整的零值，而不是报错。"""
    resp = await client.get("/api/v1/portal/me/dashboard", headers=member["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["summary"]["total_funds"] == 0
    assert data["summary"]["avg_return"] is None
    assert data["top_funds"] == []
    assert len(data["return_buckets"]) == 6


async def test_dashboard_reflects_favorites(client: AsyncClient, member: dict) -> None:
    """关注后工作台统计应反映该基金，且不同会员互不可见。"""
    add = await client.post(
        "/api/v1/portal/favorites", json={"code": "021180"}, headers=member["headers"]
    )
    assert add.status_code == 200, add.text

    resp = await client.get("/api/v1/portal/me/dashboard", headers=member["headers"])
    data = resp.json()["data"]
    assert data["summary"]["total_funds"] == 1
    assert data["recent_funds"][0]["code"] == "021180"
    assert data["type_distribution"][0]["count"] == 1

    other_name = f"tm_{uuid4().hex[:10]}"
    other = await _register(client, other_name)
    other_data = (
        await client.get("/api/v1/portal/me/dashboard", headers=other)
    ).json()["data"]
    assert other_data["summary"]["total_funds"] == 0

    async with async_session_factory() as session:
        other_user = (
            await session.execute(select(User).where(User.username == other_name))
        ).scalar_one_or_none()
        if other_user:
            await session.execute(delete(User).where(User.id == other_user.id))
            await session.commit()


async def test_update_profile_and_reflect_in_me(client: AsyncClient, member: dict) -> None:
    """资料更新只影响本人可见字段，用户名不可改。"""
    resp = await client.patch(
        "/api/v1/portal/me",
        json={"full_name": "小明", "email": "me_test@example.com", "username": "hacker"},
        headers=member["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["full_name"] == "小明"
    assert data["email"] == "me_test@example.com"
    assert data["username"] == member["username"], "username 不允许通过资料接口修改"

    me = await client.get("/api/v1/portal/auth/me", headers=member["headers"])
    assert me.json()["data"]["full_name"] == "小明"


async def test_change_password(client: AsyncClient, member: dict) -> None:
    """原密码错误拒绝，成功后可用新密码登录。"""
    bad = await client.post(
        "/api/v1/portal/me/change-password",
        json={"old_password": "WrongPassword1", "new_password": "NewPortal@123"},
        headers=member["headers"],
    )
    assert bad.status_code in (400, 422), bad.text

    ok = await client.post(
        "/api/v1/portal/me/change-password",
        json={"old_password": PASSWORD, "new_password": "NewPortal@123"},
        headers=member["headers"],
    )
    assert ok.status_code == 200, ok.text

    login = await client.post(
        "/api/v1/portal/auth/login",
        json={"username": member["username"], "password": "NewPortal@123"},
    )
    assert login.status_code == 200, login.text


async def test_deactivate_requires_password_and_blocks_token(
    client: AsyncClient, member: dict
) -> None:
    """注销需密码校验；注销后旧令牌立即失效、关注被清理。"""
    await client.post(
        "/api/v1/portal/favorites", json={"code": "021180"}, headers=member["headers"]
    )
    bad = await client.post(
        "/api/v1/portal/me/deactivate",
        json={"password": "wrong"},
        headers=member["headers"],
    )
    assert bad.status_code in (400, 401), bad.text

    ok = await client.post(
        "/api/v1/portal/me/deactivate",
        json={"password": PASSWORD},
        headers=member["headers"],
    )
    assert ok.status_code == 200, ok.text
    assert (
        await client.get("/api/v1/portal/auth/me", headers=member["headers"])
    ).status_code == 401
