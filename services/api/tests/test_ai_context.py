"""AI 账本快照：来源分级、待确认与旧估算的区分。"""

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
from app.models.fund_position import FundPosition
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.user import User

PASSWORD = "Portal@12345"
BASE = "/api/v1/portal/me/portfolio"
CODE = "000003"


@pytest.fixture
async def member(client: AsyncClient) -> AsyncIterator[dict]:
    name = f"ai_{uuid.uuid4().hex[:10]}"
    resp = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": name, "email": f"{name}@qq.com", "password": PASSWORD},
    )
    token = resp.json()["data"]["access_token"]
    async with async_session_factory() as session:
        user_id = await session.scalar(select(User.id).where(User.username == name))
    yield {"username": name, "id": user_id, "headers": {"Authorization": f"Bearer {token}"}}

    async with async_session_factory() as session:
        if user_id:
            await session.execute(delete(FundTransaction).where(FundTransaction.user_id == user_id))
            await session.execute(
                delete(FundPortfolioFlow).where(FundPortfolioFlow.user_id == user_id)
            )
            await session.execute(delete(FundPosition).where(FundPosition.user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_ai_context_requires_login(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/ai-context")).status_code == 401


async def test_ai_context_classifies_records(client: AsyncClient, member: dict) -> None:
    imported = await client.post(
        f"{BASE}/import",
        json={
            "rows": [
                {
                    "code": CODE,
                    "confirmed_on": (date.today() - timedelta(days=30)).isoformat(),
                    "shares": "1000",
                    "amount": "1200",
                    "nav": "1.2",
                    "platform": "支付宝",
                }
            ]
        },
        headers=member["headers"],
    )
    assert imported.status_code == 200, imported.text

    await client.post(
        f"{BASE}/flows",
        json={
            "code": CODE,
            "kind": "dividend",
            "effective_on": (date.today() - timedelta(days=10)).isoformat(),
            "cash_amount": "12.5",
        },
        headers=member["headers"],
    )

    # 旧版持仓：模拟迁移前的数据
    async with async_session_factory() as session:
        fund_id = await session.scalar(select(Fund.id).where(Fund.code == CODE))
        session.add(
            FundPosition(
                user_id=member["id"],
                fund_id=fund_id,
                amount=Decimal("500.00"),
                cost_nav=Decimal("1.1000"),
                bought_at=date.today() - timedelta(days=90),
            )
        )
        await session.commit()

    resp = await client.get(f"{BASE}/ai-context", headers=member["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["member"]["id"] == member["id"]
    summary = data["summary"]
    assert summary["imported"] == 1
    assert summary["legacy"] == 1
    assert summary["flows"] == 1
    assert summary["receipt"] == 0

    record = data["records"][0]
    assert record["confidence"] == "import"
    assert record["platform"] == "支付宝"
    assert record["provenance"]["record_source"] == "import"
    assert record["confirmed_on"]
    assert record["correction"] is None

    assert data["legacy"][0]["confidence"] == "legacy"
    assert data["flows"][0]["confidence"] == "manual"
    assert any("平台回执" in note for note in data["notes"])


async def test_ai_context_is_member_scoped(client: AsyncClient, member: dict) -> None:
    await client.post(
        f"{BASE}/import",
        json={
            "rows": [
                {
                    "code": CODE,
                    "confirmed_on": (date.today() - timedelta(days=5)).isoformat(),
                    "shares": "10",
                    "nav": "1.2",
                }
            ]
        },
        headers=member["headers"],
    )

    other_name = f"ax_{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/api/v1/portal/auth/register",
        json={"username": other_name, "email": f"{other_name}@qq.com", "password": PASSWORD},
    )
    other = {"Authorization": f"Bearer {reg.json()['data']['access_token']}"}

    data = (await client.get(f"{BASE}/ai-context", headers=other)).json()["data"]
    assert data["records"] == []
    assert data["summary"]["imported"] == 0

    async with async_session_factory() as session:
        other_id = await session.scalar(select(User.id).where(User.username == other_name))
        await session.execute(delete(FundTransaction).where(FundTransaction.user_id == other_id))
        await session.execute(delete(User).where(User.id == other_id))
        await session.commit()
