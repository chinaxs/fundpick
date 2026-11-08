"""门户会员注册登录测试。

重点验证"两套身份互不通用"：
门户注册的账号不能登入后台，门户 token 调不动 `/admin/**`。
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.auth_session import AuthLoginAttempt, AuthSession
from app.models.user import User
from app.services.login_limiter import MAX_FAILURES, login_key

PASSWORD = "Portal@12345"


@pytest.fixture
async def username() -> AsyncIterator[str]:
    """唯一用户名，测试结束后清理，避免污染开发库。"""
    name = f"tp_{uuid.uuid4().hex[:10]}"
    yield name
    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        if user_id is not None:
            await session.execute(
                delete(AuthSession).where(
                    AuthSession.scope == "portal", AuthSession.subject_id == user_id
                )
            )
        for scope in ("portal", "staff"):
            await session.execute(
                delete(AuthLoginAttempt).where(
                    AuthLoginAttempt.key_hash == login_key(scope, name, "127.0.0.1")
                )
            )
        await session.execute(delete(User).where(User.username == name))
        await session.commit()


async def _register(client: AsyncClient, name: str) -> dict:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def test_register_returns_token_and_me(client: AsyncClient, username: str) -> None:
    data = await _register(client, username)
    assert data["access_token"]

    resp = await client.get(
        "/api/v1/portal/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["username"] == username
    # 门户响应不应泄露后台字段
    assert "is_staff" not in body
    assert "is_superuser" not in body


async def test_duplicate_username_rejected(client: AsyncClient, username: str) -> None:
    await _register(client, username)
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert resp.status_code == 409


async def test_weak_password_rejected(client: AsyncClient, username: str) -> None:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": username, "password": "123"},
    )
    assert resp.status_code == 422


async def test_portal_account_cannot_login_admin(client: AsyncClient, username: str) -> None:
    """门户会员不能用同一套账号密码登入后台。"""
    await _register(client, username)
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert resp.status_code == 401
    # 提示与密码错误一致，不暴露"该账号不是后台账号"
    assert "用户名或密码错误" in resp.json()["message"]


async def test_portal_token_cannot_access_admin_api(client: AsyncClient, username: str) -> None:
    """即使拿到有效 token，也不能调用后台接口（scope 不匹配直接 401）。"""
    data = await _register(client, username)
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    for path in ("/api/v1/admin/articles", "/api/v1/admin/funds", "/api/v1/admin/ai/status"):
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 401, f"{path} 应拒绝门户 token，实际 {resp.status_code}"


async def test_staff_account_cannot_login_portal(client: AsyncClient) -> None:
    """后台员工账号不在 users 表，登不进门户——账号体系彻底分离。"""
    # 这个用例每次都用同一个账号名，反复跑会把失败次数堆到限频阈值；
    # 先清掉历史失败，断言才稳定落在"账号体系不通用"这一条上。
    async with async_session_factory() as session:
        await session.execute(delete(AuthLoginAttempt))
        await session.commit()
    resp = await client.post(
        "/api/v1/portal/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert resp.status_code == 401


async def test_portal_login_wrong_password(client: AsyncClient, username: str) -> None:
    await _register(client, username)
    resp = await client.post(
        "/api/v1/portal/auth/login",
        json={"username": username, "password": "Wrong@12345"},
    )
    assert resp.status_code == 401


async def test_refresh_rotation_and_logout_revoke_access(
    client: AsyncClient, username: str
) -> None:
    first = await _register(client, username)
    refreshed = await client.post(
        "/api/v1/portal/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    second = refreshed.json()["data"]
    assert second["refresh_token"] != first["refresh_token"]

    replay = await client.post(
        "/api/v1/portal/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401
    assert (
        await client.get(
            "/api/v1/portal/auth/me",
            headers={"Authorization": f"Bearer {first['access_token']}"},
        )
    ).status_code == 200

    logged_out = await client.post(
        "/api/v1/portal/auth/logout", json={"refresh_token": second["refresh_token"]}
    )
    assert logged_out.status_code == 200
    for token in (first["access_token"], second["access_token"]):
        response = await client.get(
            "/api/v1/portal/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
    assert (
        await client.post(
            "/api/v1/portal/auth/refresh", json={"refresh_token": second["refresh_token"]}
        )
    ).status_code == 401


async def test_login_failures_are_rate_limited(client: AsyncClient, username: str) -> None:
    await _register(client, username)
    for attempt in range(MAX_FAILURES):
        response = await client.post(
            "/api/v1/portal/auth/login",
            json={"username": username, "password": "Wrong@12345"},
        )
        assert response.status_code == 401, (
            f"第 {attempt + 1} 次失败尝试应返回 401，实际 {response.status_code}"
        )
    blocked = await client.post(
        "/api/v1/portal/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert blocked.status_code == 429, blocked.text
