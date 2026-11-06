"""门户会员注册登录测试。

重点验证"两套身份互不通用"：
门户注册的账号不能登入后台，门户 token 调不动 `/admin/**`。
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.session import async_session_factory
from app.models.user import User

PASSWORD = "Portal@12345"


@pytest.fixture
async def username() -> AsyncIterator[str]:
    """唯一用户名，测试结束后清理，避免污染开发库。"""
    name = f"tp_{uuid.uuid4().hex[:10]}"
    yield name
    async with async_session_factory() as session:
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
