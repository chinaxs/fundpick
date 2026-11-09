"""会员支持：反馈、密码重置、只读排查与查看审计。

重点是"两条闭环"：
- 反馈提交 → 后台处理 → 会员能看到回复；
- 会员申请重置 → 客服生成一次性链接 → 用链接改密 → 旧密码失效、旧会话失效。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.models.support import Feedback, PasswordResetRequest
from app.models.user import User

PASSWORD = "Portal@12345"
ADMIN_PASSWORD = "Admin@123456"
STAFF_PASSWORD = "Staff@12345"
FEEDBACK = "/api/v1/portal/feedback"
SUPPORT = "/api/v1/admin/support"


async def _login_admin(client: AsyncClient) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/admin/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def _register(client: AsyncClient, name: str) -> tuple[str, dict[str, str]]:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def member(client: AsyncClient) -> AsyncIterator[dict]:
    name = f"ts_{uuid.uuid4().hex[:10]}"
    token, headers = await _register(client, name)
    yield {"username": name, "email": f"{name}@example.com", "token": token, "headers": headers}

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == name))
        ).scalar_one_or_none()
        if user:
            await session.execute(delete(Feedback).where(Feedback.user_id == user.id))
            await session.execute(
                delete(PasswordResetRequest).where(PasswordResetRequest.user_id == user.id)
            )
            await session.execute(
                delete(AuditLog).where(
                    AuditLog.resource == "member_portfolio", AuditLog.resource_id == str(user.id)
                )
            )
            await session.execute(
                delete(AuthSession).where(
                    AuthSession.scope == "portal", AuthSession.subject_id == user.id
                )
            )
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def test_feedback_requires_login(client: AsyncClient) -> None:
    assert (await client.post(FEEDBACK, json={"title": "x", "content": "y"})).status_code == 401
    assert (await client.get(FEEDBACK)).status_code == 401


async def test_feedback_roundtrip(client: AsyncClient, member: dict) -> None:
    admin = await _login_admin(client)
    created = await client.post(
        FEEDBACK,
        json={
            "category": "data",
            "title": "净值日期不对",
            "content": "某基金净值显示的是上周五的数据，希望确认一下。",
            "page_url": "/funds/002910",
        },
        headers=member["headers"],
    )
    assert created.status_code == 201, created.text
    feedback = created.json()["data"]
    assert feedback["status"] == "open"

    mine = await client.get(FEEDBACK, headers=member["headers"])
    assert [item["id"] for item in mine.json()["data"]] == [feedback["id"]]

    listing = await client.get(f"{SUPPORT}/feedback", params={"status": "open"}, headers=admin)
    assert listing.status_code == 200, listing.text
    rows = listing.json()["data"]["items"]
    row = next(item for item in rows if item["id"] == feedback["id"])
    assert row["username"] == member["username"]
    assert row["email"] == member["email"]

    updated = await client.patch(
        f"{SUPPORT}/feedback/{feedback['id']}",
        json={"status": "resolved", "reply": "已重新采集，请刷新确认"},
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["handled_by"] == "admin"

    # 会员侧能看到回复
    mine = await client.get(FEEDBACK, headers=member["headers"])
    assert mine.json()["data"][0]["reply"] == "已重新采集，请刷新确认"


async def test_feedback_rejects_unknown_category(client: AsyncClient, member: dict) -> None:
    resp = await client.post(
        FEEDBACK,
        json={"category": "rm -rf", "title": "测试标题", "content": "这是一个足够长的描述文本。"},
        headers=member["headers"],
    )
    assert resp.status_code == 422


async def test_support_endpoints_are_superuser_only(client: AsyncClient, member: dict) -> None:
    admin = await _login_admin(client)
    name = f"tu_{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/admin/staff",
        json={"username": name, "password": STAFF_PASSWORD},
        headers=admin,
    )
    assert created.status_code in (200, 201), created.text
    staff_id = created.json()["data"]["id"]
    login = await client.post(
        "/api/v1/admin/auth/login", json={"username": name, "password": STAFF_PASSWORD}
    )
    staff = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    assert (await client.get(f"{SUPPORT}/feedback", headers=staff)).status_code == 403
    assert (await client.get(f"{SUPPORT}/members/1", headers=staff)).status_code == 403
    await client.delete(f"/api/v1/admin/staff/{staff_id}", headers=admin)


async def test_forgot_password_does_not_leak_accounts(client: AsyncClient, member: dict) -> None:
    user_id = await _user_id(member["username"])
    async with async_session_factory() as session:
        before = len(
            (
                await session.execute(
                    select(PasswordResetRequest.id).where(PasswordResetRequest.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )

    known = await client.post(
        "/api/v1/portal/auth/forgot-password", json={"account": member["email"]}
    )
    unknown = await client.post(
        "/api/v1/portal/auth/forgot-password",
        json={"account": f"nobody_{uuid.uuid4().hex[:6]}@example.com"},
    )
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]

    async with async_session_factory() as session:
        after = len(
            (
                await session.execute(
                    select(PasswordResetRequest.id).where(PasswordResetRequest.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
    assert after == before + 1


async def test_reset_link_flow_revokes_old_password_and_sessions(
    client: AsyncClient, member: dict
) -> None:
    admin = await _login_admin(client)
    requested = await client.post(
        "/api/v1/portal/auth/forgot-password", json={"account": member["username"]}
    )
    assert requested.status_code == 200

    pending = await client.get(
        f"{SUPPORT}/password-resets", params={"status": "pending"}, headers=admin
    )
    assert any(row["username"] == member["username"] for row in pending.json()["data"])

    link = await client.post(
        f"{SUPPORT}/members/{await _user_id(member['username'])}/reset-link", headers=admin
    )
    assert link.status_code == 200, link.text
    token = link.json()["data"]["token"]
    assert token not in {"", None}

    new_password = "NewPortal@98765"
    reset = await client.post(
        "/api/v1/portal/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert reset.status_code == 200, reset.text

    # 旧密码失效，新密码可用
    old_login = await client.post(
        "/api/v1/portal/auth/login",
        json={"username": member["username"], "password": PASSWORD},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/portal/auth/login",
        json={"username": member["username"], "password": new_password},
    )
    assert new_login.status_code == 200

    # 旧令牌不能用：重置后全部会话被撤销
    me = await client.get("/api/v1/portal/auth/me", headers=member["headers"])
    assert me.status_code == 401

    # 令牌一次性
    reuse = await client.post(
        "/api/v1/portal/auth/reset-password",
        json={"token": token, "new_password": "Another@12345"},
    )
    assert reuse.status_code in (400, 422)


async def test_expired_reset_link_rejected(client: AsyncClient, member: dict) -> None:
    admin = await _login_admin(client)
    user_id = await _user_id(member["username"])
    link = await client.post(f"{SUPPORT}/members/{user_id}/reset-link", headers=admin)
    token = link.json()["data"]["token"]

    async with async_session_factory() as session:
        row = (
            (
                await session.execute(
                    select(PasswordResetRequest).where(PasswordResetRequest.user_id == user_id)
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        row.expires_at = datetime.now() - timedelta(minutes=1)
        await session.commit()

    resp = await client.post(
        "/api/v1/portal/auth/reset-password",
        json={"token": token, "new_password": "Another@12345"},
    )
    assert resp.status_code in (400, 422)


async def test_member_overview_counts(client: AsyncClient, member: dict) -> None:
    admin = await _login_admin(client)
    user_id = await _user_id(member["username"])
    await client.post(
        FEEDBACK,
        json={
            "category": "account",
            "title": "登录问题",
            "content": "我登录后马上又退出，麻烦看下。",
        },
        headers=member["headers"],
    )
    resp = await client.get(f"{SUPPORT}/members/{user_id}", headers=admin)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["username"] == member["username"]
    assert data["open_feedback"] == 1
    assert data["transaction_count"] == 0

    missing = await client.get(f"{SUPPORT}/members/99999999", headers=admin)
    assert missing.status_code == 404


async def test_portfolio_view_is_read_only_and_audited(client: AsyncClient, member: dict) -> None:
    admin = await _login_admin(client)
    user_id = await _user_id(member["username"])

    resp = await client.get(f"{SUPPORT}/members/{user_id}/portfolio", headers=admin)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["user_id"] == user_id
    assert data["note"].startswith("只读排查视图")

    async with async_session_factory() as session:
        log = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.resource == "member_portfolio",
                        AuditLog.resource_id == str(user_id),
                        AuditLog.action == "read",
                    )
                )
            )
            .scalars()
            .first()
        )
    assert log is not None
    assert log.username == "admin"

    # 只读：没有提供任何写接口
    assert (
        await client.post(f"{SUPPORT}/members/{user_id}/portfolio", headers=admin)
    ).status_code == 405


async def _user_id(username: str) -> int:
    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == username))
    assert user_id is not None
    return int(user_id)
