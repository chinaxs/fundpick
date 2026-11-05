"""后台运营接口与审计日志测试。

覆盖：权限边界（匿名 / 门户会员 / 后台账号 / 超管）、仪表盘字段、审计记录落库。
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.session import async_session_factory
from app.models.audit_log import AuditLog
from app.models.user import User

PASSWORD = "Admin@123456"
STAFF_PASSWORD = "Staff@12345"


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/admin/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, "admin", PASSWORD)


@pytest.fixture
async def staff_account(client: AsyncClient, admin_headers: dict[str, str]) -> AsyncIterator[dict]:
    """创建一个「是后台账号但不是超管」的用户，用于验证权限分层。"""
    name = f"ts_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/admin/users",
        json={"username": name, "password": STAFF_PASSWORD, "is_staff": True},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    user_id = resp.json()["data"]["id"]

    headers = await _login(client, name, STAFF_PASSWORD)
    yield {"username": name, "id": user_id, "headers": headers}

    async with async_session_factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.username == name))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_dashboard_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/dashboard")).status_code == 401


async def test_dashboard_rejects_portal_member(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    name = f"tp_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/portal/auth/register", json={"username": name, "password": PASSWORD}
    )
    token = resp.json()["data"]["access_token"]

    try:
        result = await client.get(
            "/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"}
        )
        assert result.status_code == 403
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(User).where(User.username == name))
            await session.commit()


async def test_dashboard_shape(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["funds_total"] > 0
    assert data["coverage"], "覆盖率不能为空"
    # 覆盖率必须有真实值，不能全是 0（曾因 SUM(布尔) 变成 1 而全部显示 0%）
    assert any(item["covered"] > 0 for item in data["coverage"])

    for item in data["coverage"]:
        assert 0 <= item["percent"] <= 100
        assert item["covered"] <= item["total"]


async def test_system_info_requires_superuser(
    client: AsyncClient, admin_headers: dict[str, str], staff_account: dict
) -> None:
    # 超管可访问
    ok = await client.get("/api/v1/admin/system/info", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["data"]["tables"]

    # 后台账号但非超管不可访问
    denied = await client.get("/api/v1/admin/system/info", headers=staff_account["headers"])
    assert denied.status_code == 403


async def test_audit_log_records_write_operation(
    client: AsyncClient, admin_headers: dict[str, str], staff_account: dict
) -> None:
    """改一次用户资料，审计里应出现这条记录。"""
    target = staff_account["id"]
    resp = await client.patch(
        f"/api/v1/admin/users/{target}",
        json={"full_name": "审计测试"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    logs = await client.get(
        "/api/v1/admin/audit-logs", params={"resource": "users"}, headers=admin_headers
    )
    assert logs.status_code == 200
    items = logs.json()["data"]["items"]
    assert items, "应至少有一条 users 相关审计"

    latest = items[0]
    assert latest["username"] == "admin"
    assert latest["action"] == "update"
    assert latest["method"] == "PATCH"
    assert latest["status_code"] == 200
    assert latest["resource_id"] == str(target)


async def test_audit_logs_requires_superuser(client: AsyncClient, staff_account: dict) -> None:
    resp = await client.get("/api/v1/admin/audit-logs", headers=staff_account["headers"])
    assert resp.status_code == 403


async def test_user_batch_delete_protects_self(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """批量删除不能删掉操作者本人。"""
    import sqlalchemy as sa

    async with async_session_factory() as session:
        admin_id = (
            (await session.execute(sa.select(User.id).where(User.username == "admin")))
            .scalar_one()
        )

    resp = await client.post(
        "/api/v1/admin/users/batch-delete",
        json={"ids": [admin_id]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["affected"] == 0

    async with async_session_factory() as session:
        admin = await session.get(User, admin_id)
        assert admin is not None and admin.deleted_at is None


async def test_article_batch_status_and_delete(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """批量发布 / 撤回 / 删除文章，affected 数与实际行数一致。"""
    ids = []
    for i in range(2):
        resp = await client.post(
            "/api/v1/admin/articles",
            json={"title": f"批量测试 {uuid.uuid4().hex[:6]} {i}", "content": "x"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["data"]["id"])

    try:
        published = await client.post(
            "/api/v1/admin/articles/batch-status",
            json={"ids": ids, "status": "published"},
            headers=admin_headers,
        )
        assert published.status_code == 200
        assert published.json()["data"]["affected"] == 2

        withdrawn = await client.post(
            "/api/v1/admin/articles/batch-status",
            json={"ids": ids, "status": "draft"},
            headers=admin_headers,
        )
        assert withdrawn.json()["data"]["affected"] == 2
    finally:
        removed = await client.post(
            "/api/v1/admin/articles/batch-delete",
            json={"ids": ids},
            headers=admin_headers,
        )
        assert removed.status_code == 200
        assert removed.json()["data"]["affected"] == 2


async def test_batch_requires_staff(client: AsyncClient) -> None:
    """匿名调用批量接口应 401，防越权。"""
    resp = await client.post(
        "/api/v1/admin/articles/batch-delete", json={"ids": [1]}
    )
    assert resp.status_code == 401
