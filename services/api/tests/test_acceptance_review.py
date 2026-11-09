"""Independent acceptance checks for account recovery and real-account bookkeeping."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from test_portfolio_flow import BASE, DAY, buy, commit
from test_portfolio_flow import book as book

from app.db.session import async_session_factory
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.support import PasswordResetRequest
from app.services.password_reset import PasswordResetService


def test_content_assistant_does_not_expose_private_portfolio_tool():
    from app.ai.tools import ALL_TOOLS

    assert "portfolio_evidence" not in {tool.name for tool in ALL_TOOLS}


@pytest.fixture
async def audit_book(client, book):
    me = await client.get("/api/v1/portal/auth/me", headers=book["headers"])
    user_id = me.json()["data"]["id"]
    yield {**book, "user_id": user_id}
    async with async_session_factory() as session:
        await session.execute(delete(FundPortfolioFlow).where(FundPortfolioFlow.user_id == user_id))
        await session.execute(
            delete(PasswordResetRequest).where(PasswordResetRequest.user_id == user_id)
        )
        await session.commit()


async def reconciliation(client, book):
    response = await client.get(BASE + "/portfolio/reconciliation", headers=book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_reconciliation_sums_all_platforms(client, audit_book):
    for platform in ("A", "B"):
        await commit(
            client, audit_book, buy(audit_book, record_source="estimated", platform=platform)
        )
    data = await reconciliation(client, audit_book)
    assert data["funds"][0]["ledger_shares"] == 1000
    assert data["funds"][0]["ledger_cost"] == 2020


async def test_import_keeps_platform_snapshots_separate_and_orders_dates(client, audit_book):
    rows = [
        {"platform": "A", "confirmed_on": str(DAY), "shares": "100", "amount": "200"},
        {
            "platform": "B",
            "confirmed_on": str(DAY - timedelta(days=1)),
            "shares": "300",
            "amount": "600",
        },
        {
            "platform": "A",
            "confirmed_on": str(DAY - timedelta(days=2)),
            "shares": "50",
            "amount": "100",
        },
    ]
    response = await client.post(
        BASE + "/portfolio/import",
        json={"rows": [{"code": audit_book["code"], **row} for row in rows]},
        headers=audit_book["headers"],
    )
    assert response.status_code == 200, response.text
    async with async_session_factory() as session:
        transactions = list(
            (
                await session.execute(
                    select(FundTransaction)
                    .where(FundTransaction.user_id == audit_book["user_id"])
                    .order_by(FundTransaction.confirmed_on, FundTransaction.id)
                )
            ).scalars()
        )
        assert [(tx.platform, float(tx.remaining_shares)) for tx in transactions] == [
            ("A", 50),
            ("B", 300),
            ("A", 150),
        ]


async def test_split_ratio_is_applied_at_event_date(client, audit_book):
    await commit(client, audit_book, buy(audit_book))
    response = await client.post(
        BASE + "/portfolio/flows",
        json={"code": audit_book["code"], "kind": "split", "effective_on": str(DAY), "ratio": "2"},
        headers=audit_book["headers"],
    )
    assert response.status_code == 201, response.text
    data = await reconciliation(client, audit_book)
    assert data["funds"][0]["expected_shares"] == 1000


async def test_reinvestment_rejects_negative_shares(client, audit_book):
    response = await client.post(
        BASE + "/portfolio/flows",
        json={
            "code": audit_book["code"],
            "kind": "reinvest",
            "effective_on": str(DAY),
            "shares_delta": "-10",
        },
        headers=audit_book["headers"],
    )
    assert response.status_code == 422, response.text


async def test_reset_token_can_only_be_used_once_under_concurrency(client, audit_book):
    async with async_session_factory() as session:
        link = await PasswordResetService(session).issue_link(audit_book["user_id"], "review")
    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/portal/auth/reset-password",
                json={"token": link.token, "new_password": f"NewPortal@9876{index}"},
            )
            for index in range(2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 422]


async def test_reissuing_reset_link_invalidates_previous_link(client, audit_book):
    async with async_session_factory() as session:
        service = PasswordResetService(session)
        first = await service.issue_link(audit_book["user_id"], "review")
        await service.issue_link(audit_book["user_id"], "review")
    response = await client.post(
        "/api/v1/portal/auth/reset-password",
        json={"token": first.token, "new_password": "NewPortal@98765"},
    )
    assert response.status_code == 422, response.text


async def test_issuing_reset_link_resolves_pending_request(audit_book):
    async with async_session_factory() as session:
        session.add(PasswordResetRequest(user_id=audit_book["user_id"]))
        await session.commit()
        await PasswordResetService(session).issue_link(audit_book["user_id"], "review")
    async with async_session_factory() as session:
        pending = (
            (
                await session.execute(
                    select(PasswordResetRequest.id).where(
                        PasswordResetRequest.user_id == audit_book["user_id"],
                        PasswordResetRequest.token_hash.is_(None),
                        PasswordResetRequest.used_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert pending == []


async def test_schedule_claim_survives_fast_job_completion(monkeypatch):
    from datetime import datetime

    from app.core.exceptions import ConflictError
    from app.models.sync_job import SyncJob, SyncSchedule
    from app.schemas.sync_job import SyncTriggerRequest
    from app.services.sync_job import SyncJobService

    async def instant_job(self, job, payload):
        job.status = "success"
        await self.session.commit()

    monkeypatch.setattr(SyncJobService, "spawn", instant_job)
    async with async_session_factory() as session:
        schedule = SyncSchedule(mode="news", hour=0, minute=0, weekdays="", enabled=True)
        session.add(schedule)
        await session.commit()
        schedule_id = schedule.id
    try:
        async with async_session_factory() as session:
            first = await SyncJobService(session).start(
                SyncTriggerRequest(mode="news"),
                "acceptance-review",
                schedule_id=schedule_id,
                scheduled_on=datetime.now().date(),
            )
            assert first.status == "success"
        async with async_session_factory() as session:
            with pytest.raises(ConflictError):
                await SyncJobService(session).start(
                    SyncTriggerRequest(mode="news"),
                    "acceptance-review",
                    schedule_id=schedule_id,
                    scheduled_on=datetime.now().date(),
                )
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(SyncSchedule).where(SyncSchedule.id == schedule_id))
            await session.execute(
                delete(SyncJob).where(SyncJob.triggered_by == "acceptance-review")
            )
            await session.commit()
