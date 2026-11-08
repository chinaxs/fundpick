"""运营效果指标：访问活跃口径、测试帐号过滤与留存窗口。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.auth_session import AuthSession
from app.models.fund import Fund
from app.models.fund_transaction import FundTransaction
from app.models.member_activity import MemberActivity
from app.models.user import User
from app.services.member_activity import reset_throttle

BASE = "/api/v1/admin/dashboard/engagement"
PASSWORD = "Portal@12345"


async def _admin(client: AsyncClient) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/admin/auth/login", json={"username": "admin", "password": "Admin@123456"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture(autouse=True)
def _clear_throttle() -> None:
    reset_throttle()


@pytest.fixture
async def cleanup() -> AsyncIterator[list[str]]:
    """记录本用例创建的会员名，结束后连同会话、访问记录一起删除。"""
    names: list[str] = []
    yield names
    async with async_session_factory() as session:
        for name in names:
            user_id = await session.scalar(select(User.id).where(User.username == name))
            if user_id is None:
                continue
            await session.execute(
                delete(AuthSession).where(
                    AuthSession.scope == "portal", AuthSession.subject_id == user_id
                )
            )
            await session.execute(delete(MemberActivity).where(MemberActivity.user_id == user_id))
            await session.execute(delete(FundTransaction).where(FundTransaction.user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def _register(client: AsyncClient, name: str, email: str) -> str:
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def test_engagement_requires_login(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


async def test_visit_counts_as_active_and_test_accounts_are_excluded(
    client: AsyncClient, cleanup: list[str]
) -> None:
    admin = await _admin(client)
    before = (await client.get(BASE, headers=admin)).json()["data"]

    real_name = f"u{uuid.uuid4().hex[:10]}"
    cleanup.append(real_name)
    token = await _register(client, real_name, f"{real_name}@qq.com")
    # 注册本身不算访问：必须有一次带登录态的页面/接口访问
    visit = await client.get(
        "/api/v1/portal/me/portfolio", headers={"Authorization": f"Bearer {token}"}
    )
    assert visit.status_code == 200, visit.text

    fake_name = f"ts_{uuid.uuid4().hex[:10]}"
    cleanup.append(fake_name)
    await _register(client, fake_name, f"{fake_name}@example.com")

    after = (await client.get(BASE, headers=admin)).json()["data"]

    assert after["total_users"] == before["total_users"] + 1
    assert after["new_7d"] == before["new_7d"] + 1
    assert after["active_7d"] == before["active_7d"] + 1
    assert after["total_users"] < before["total_users"] + 2

    assert after["excluded_note"]
    assert "访问" in after["definitions"]
    assert isinstance(after["daily_active"], list)


async def test_underscore_prefix_does_not_swallow_real_accounts(
    client: AsyncClient, cleanup: list[str]
) -> None:
    """`ts_` 里的下划线不能当 LIKE 通配符，否则 "tsa..." 会被误排除。"""
    admin = await _admin(client)
    before = (await client.get(BASE, headers=admin)).json()["data"]

    lookalike = f"tsa_{uuid.uuid4().hex[:8]}"
    cleanup.append(lookalike)
    await _register(client, lookalike, f"{lookalike}@qq.com")

    after = (await client.get(BASE, headers=admin)).json()["data"]
    assert after["total_users"] == before["total_users"] + 1


async def test_returning_needs_two_distinct_days(client: AsyncClient, cleanup: list[str]) -> None:
    admin = await _admin(client)
    name = f"r{uuid.uuid4().hex[:10]}"
    cleanup.append(name)
    await _register(client, name, f"{name}@qq.com")

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        today = date.today()
        session.add_all(
            [
                MemberActivity(user_id=user_id, activity_date=today, last_seen_at=datetime.now()),
                MemberActivity(
                    user_id=user_id,
                    activity_date=today - timedelta(days=1),
                    last_seen_at=datetime.now(),
                ),
            ]
        )
        await session.commit()

    data = (await client.get(BASE, headers=admin)).json()["data"]
    assert data["returning_7d"] >= 1


async def test_retention_cohort_is_seven_to_fourteen_days(
    client: AsyncClient, cleanup: list[str]
) -> None:
    admin = await _admin(client)
    name = f"c{uuid.uuid4().hex[:10]}"
    cleanup.append(name)
    await _register(client, name, f"{name}@qq.com")

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        user = await session.get(User, user_id)
        assert user is not None
        user.created_at = datetime.now() - timedelta(days=9)  # 落在 7–14 天队列
        session.add(
            MemberActivity(user_id=user_id, activity_date=date.today(), last_seen_at=datetime.now())
        )
        await session.commit()

    data = (await client.get(BASE, headers=admin)).json()["data"]
    assert data["retention_cohort"] >= 1
    assert data["retention_7d"] >= 1
    assert data["retention_7d"] <= data["retention_cohort"]


async def test_voided_transaction_does_not_count_as_conversion(
    client: AsyncClient, cleanup: list[str]
) -> None:
    admin = await _admin(client)
    name = f"v{uuid.uuid4().hex[:10]}"
    cleanup.append(name)
    await _register(client, name, f"{name}@qq.com")

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        fund_id = await session.scalar(select(Fund.id).limit(1))
        session.add(
            FundTransaction(
                user_id=user_id,
                fund_id=fund_id,
                kind="buy",
                status="voided",
                confirmed_on=date.today(),
                nav=1,
                nav_source="manual",
                amount=100,
                fee=0,
                shares=100,
                cash_amount=100,
                realized_profit=0,
                remaining_shares=0,
                remaining_cost=0,
                request_key=str(uuid.uuid4()),
                request_hash="x" * 64,
                voided_at=datetime.now(),
            )
        )
        await session.commit()

    before = (await client.get(BASE, headers=admin)).json()["data"]["users_with_transaction"]
    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        fund_id = await session.scalar(select(Fund.id).limit(1))
        session.add(
            FundTransaction(
                user_id=user_id,
                fund_id=fund_id,
                kind="buy",
                status="confirmed",
                confirmed_on=date.today(),
                nav=1,
                nav_source="manual",
                amount=100,
                fee=0,
                shares=100,
                cash_amount=100,
                realized_profit=0,
                remaining_shares=100,
                remaining_cost=100,
                request_key=str(uuid.uuid4()),
                request_hash="y" * 64,
            )
        )
        await session.commit()

    after = (await client.get(BASE, headers=admin)).json()["data"]["users_with_transaction"]
    assert after == before + 1


DOMAINS = ("example.com", "test.local", "localhost")


async def test_every_test_email_domain_is_excluded(client: AsyncClient, cleanup: list[str]) -> None:
    """三个测试域名都要排掉：条件写成 OR 会恒真，一个也排不掉。"""
    admin = await _admin(client)
    before = (await client.get(BASE, headers=admin)).json()["data"]["total_users"]

    for index, domain in enumerate(DOMAINS):
        name = f"dm{index}{uuid.uuid4().hex[:8]}"
        cleanup.append(name)
        token = await _register(client, name, f"{name}@qq.com")
        async with async_session_factory() as session:
            user_id = await session.scalar(select(User.id).where(User.username == name))
            user = await session.get(User, user_id)
            assert user is not None
            user.email = f"{uuid.uuid4().hex[:8]}@{domain}"
            await session.commit()
        # 访问一次，确认即使活跃也不会计入
        await client.get(
            "/api/v1/portal/me/portfolio", headers={"Authorization": f"Bearer {token}"}
        )

    after = (await client.get(BASE, headers=admin)).json()["data"]["total_users"]
    assert after == before


@pytest.mark.parametrize(
    ("days_ago", "window", "included"),
    [
        (6, 7, True),
        (7, 7, False),
        (13, 14, True),
        (14, 14, False),
        (29, 30, True),
        (30, 30, False),
    ],
)
async def test_activity_window_boundaries(
    client: AsyncClient,
    cleanup: list[str],
    days_ago: int,
    window: int,
    included: bool,
) -> None:
    """含今天在内的 N 个自然日：today-(N-1) 在内，today-N 不在。"""
    from app.repositories.engagement import EngagementRepository

    async with async_session_factory() as session:
        before = await EngagementRepository(session).active_users(window)

    name = f"b{days_ago}_{uuid.uuid4().hex[:8]}"
    cleanup.append(name)
    await _register(client, name, f"{name}@qq.com")
    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        session.add(
            MemberActivity(
                user_id=user_id,
                activity_date=date.today() - timedelta(days=days_ago),
                last_seen_at=datetime.now() - timedelta(days=days_ago),
            )
        )
        await session.commit()

    async with async_session_factory() as session:
        after = await EngagementRepository(session).active_users(window)
    assert after == before + (1 if included else 0)


async def test_same_token_on_two_days_counts_as_returning(
    client: AsyncClient, cleanup: list[str]
) -> None:
    """同一 token 隔天再来：要新增一行访问记录并算回访，而不是只算首次登录。"""
    admin = await _admin(client)
    name = f"t{uuid.uuid4().hex[:10]}"
    cleanup.append(name)
    token = await _register(client, name, f"{name}@qq.com")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        session.add(
            MemberActivity(
                user_id=user_id,
                activity_date=date.today() - timedelta(days=1),
                last_seen_at=datetime.now() - timedelta(days=1),
            )
        )
        await session.commit()

    before = (await client.get(BASE, headers=admin)).json()["data"]["returning_7d"]
    reset_throttle()
    visit = await client.get("/api/v1/portal/me/portfolio", headers=headers)
    assert visit.status_code == 200, visit.text

    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
        days = (
            (
                await session.execute(
                    select(MemberActivity.activity_date).where(MemberActivity.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
    assert sorted(days) == [date.today() - timedelta(days=1), date.today()]

    after = (await client.get(BASE, headers=admin)).json()["data"]["returning_7d"]
    assert after == before + 1
