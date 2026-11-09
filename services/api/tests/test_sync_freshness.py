"""Trading-calendar freshness and durable automatic posting without browser activity."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_portfolio_flow import DAY
from test_portfolio_flow import book as book
from test_trade_fees import RULES

from app.datasources.fund_fees import PARSER_VERSION, parse_fee_page
from app.db.session import async_session_factory
from app.models import FundFeeSchedule, FundTransaction, SyncSchedule, TradeApplication
from app.schemas.portfolio import AutoTradeInput
from app.services import automatic_lookup, automatic_reconcile, automatic_trade
from app.services.data_freshness import expected_nav_date, freshness
from app.services.sync_schedule import RECOMMENDED_SCHEDULES, SyncScheduleService, is_due
from app.services.trade_application import ApplicationService
from app.services.trade_fee_math import fee_for


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 11, 9, 14), date(2026, 11, 6)),
        (datetime(2026, 11, 9, 21, 59), date(2026, 11, 6)),
        (datetime(2026, 11, 9, 22), date(2026, 11, 9)),
        (datetime(2026, 11, 8, 23), date(2026, 11, 6)),
        (datetime(2026, 10, 7, 23), date(2026, 9, 30)),
        (datetime(2028, 1, 5, 23), None),
    ],
)
def test_freshness_uses_beijing_calendar_and_disclosure_checkpoint(moment, expected):
    assert expected_nav_date(moment) == expected


def test_friday_to_monday_is_not_three_day_delay():
    state = freshness(date(2026, 11, 6), datetime(2026, 11, 9, 16))
    assert state["freshness_state"] == "current" and state["nav_lag_trading_days"] == 0
    delayed = freshness(date(2026, 11, 6), datetime(2026, 11, 9, 22))
    assert delayed["freshness_state"] == "lagging" and delayed["nav_lag_trading_days"] == 1
    utc = datetime(2026, 11, 9, 14, tzinfo=__import__("datetime").UTC)
    assert expected_nav_date(utc) == date(2026, 11, 9)


def test_explicit_zero_fee_generic_heading_is_parsed_without_guessing():
    html = (
        '<h4 class="t">申购费率</h4><table><tbody>'
        "<tr><td>---</td><td>0.00%</td></tr></tbody></table>"
    )
    rules = parse_fee_page(html)
    assert fee_for(rules, "buy", Decimal(1000), Decimal(1000), "")[0] == 0
    assert parse_fee_page(html.replace("0.00%", "未知"))[0]["condition"] == "---"
    assert (
        fee_for(
            parse_fee_page(html.replace("0.00%", "未知")), "buy", Decimal(1000), Decimal(1000), ""
        )
        is None
    )
    assert parse_fee_page(html.replace("申购费率", "认购费率")) == []


def test_schedule_skips_holiday_and_unknown_calendar():
    row = SyncSchedule(
        mode="snapshot", hour=18, minute=30, enabled=True, weekdays="", last_run_on=None
    )
    assert not is_due(row, datetime(2026, 10, 1, 19))
    assert not is_due(row, datetime(2028, 1, 5, 19))
    assert is_due(row, datetime(2026, 11, 9, 19))


async def test_recommended_schedule_install_is_idempotent():
    async with async_session_factory() as session:
        existing = set((await session.scalars(select(SyncSchedule.id))).all())
    try:
        async with async_session_factory() as session:
            first = await SyncScheduleService(session).install_recommended()
            second = await SyncScheduleService(session).install_recommended()
            assert {x.id for x in first} == {x.id for x in second}
            assert {(x.mode, x.hour, x.minute) for x in second} >= {
                (m, h, n) for m, h, n in RECOMMENDED_SCHEDULES
            }
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(SyncSchedule).where(SyncSchedule.id.not_in(existing)))
            await session.commit()


async def make_pending(client, book, count=1):
    user_id = (await client.get("/api/v1/portal/auth/me", headers=book["headers"])).json()["data"][
        "id"
    ]
    ids = []
    async with async_session_factory() as session:
        for _ in range(count):
            payload = AutoTradeInput(
                code=book["code"],
                kind="buy",
                amount="100",
                submitted_at=DAY.isoformat() + "T14:00:00+08:00",
                pricing_rule="auto",
                request_key=uuid4(),
            )
            created = await ApplicationService(session).create(user_id, payload)
            row = await session.get(TradeApplication, created.id)
            row.automatic_processing = True
            ids.append(created.id)
        await session.commit()
    return user_id, ids


async def test_worker_posts_without_get_requests_and_is_idempotent(client, book, monkeypatch):
    _user_id, ids = await make_pending(client, book)
    monkeypatch.setattr(automatic_trade, "lookup_nav", AsyncMock(return_value=2))
    monkeypatch.setattr(
        automatic_trade, "lookup_rules", AsyncMock(return_value=(RULES, "source", datetime.now()))
    )
    results = await asyncio.gather(
        automatic_reconcile.reconcile_due(), automatic_reconcile.reconcile_due()
    )
    assert sum(r["recorded"] for r in results) == 1
    async with async_session_factory() as session:
        tx = (
            await session.scalars(
                select(FundTransaction).where(FundTransaction.application_id == ids[0])
            )
        ).all()
        row = await session.get(TradeApplication, ids[0])
        assert len(tx) == 1 and row.status == "recorded"
        assert row.next_retry_at is None and row.last_attempt_at is not None
    assert (await automatic_reconcile.reconcile_due())["checked"] == 0


async def test_retry_backoff_does_not_starve_later_applications(client, book, monkeypatch):
    _, ids = await make_pending(client, book, 2)
    monkeypatch.setattr(automatic_trade, "lookup_nav", AsyncMock(return_value=None))
    first = await automatic_reconcile.reconcile_due(limit=1)
    second = await automatic_reconcile.reconcile_due(limit=1)
    assert first["checked"] == 1 and second["checked"] == 1
    async with async_session_factory() as session:
        rows = (
            await session.scalars(select(TradeApplication).where(TradeApplication.id.in_(ids)))
        ).all()
        assert all(row.last_attempt_at and row.next_retry_at for row in rows)
    assert (await automatic_reconcile.reconcile_due())["checked"] == 0


async def test_worker_ignores_cancelled_manual_and_deleted(client, book, monkeypatch):
    _, ids = await make_pending(client, book, 3)
    async with async_session_factory() as session:
        a, b, c = [await session.get(TradeApplication, i) for i in ids]
        a.status = "cancelled"
        b.automatic_processing = False
        c.deleted_at = datetime.now()
        await session.commit()
    resolve = AsyncMock()
    monkeypatch.setattr(automatic_reconcile.AutomaticTradeService, "resolve", resolve)
    assert (await automatic_reconcile.reconcile_due())["checked"] == 0
    resolve.assert_not_called()


async def test_worker_does_not_process_disabled_member(client, book, monkeypatch):
    from app.models.user import User

    user_id, _ = await make_pending(client, book)
    async with async_session_factory() as session:
        member = await session.get(User, user_id)
        member.is_active = False
        await session.commit()
    resolve = AsyncMock()
    monkeypatch.setattr(automatic_reconcile.AutomaticTradeService, "resolve", resolve)
    assert (await automatic_reconcile.reconcile_due())["checked"] == 0
    resolve.assert_not_called()


async def test_snapshot_source_failure_is_counted(monkeypatch):
    from types import SimpleNamespace

    from scripts import sync_funds

    failures = []

    def unavailable(category):
        raise RuntimeError("no data source")

    monkeypatch.setattr(
        sync_funds, "get_provider", lambda: SimpleNamespace(list_snapshots=unavailable)
    )
    monkeypatch.setattr(
        sync_funds, "PROGRESS", SimpleNamespace(fail=lambda item, reason: failures.append(item))
    )
    async with async_session_factory() as session:
        assert await sync_funds.sync_snapshots(session) == 0
    assert set(failures) == set(sync_funds.RANK_CATEGORIES)


async def test_fee_parser_version_invalidates_incomplete_old_cache(client, book, monkeypatch):
    async with async_session_factory() as session:
        session.add(
            FundFeeSchedule(
                fund_id=book["fund_id"],
                rules=[RULES[-1]],
                source_url="old",
                fetched_at=datetime.now(),
                parser_version=1,
            )
        )
        await session.commit()
    fresh = [{"kind": "buy", "condition": "大于等于0元", "standard": "0.00%", "discounted": ""}]
    monkeypatch.setattr(
        automatic_lookup,
        "get_provider",
        lambda: type("P", (), {"transaction_fees": lambda self, code: fresh})(),
    )
    automatic_lookup._attempts.clear()
    try:
        rules, _, _ = await automatic_lookup.lookup_rules(book["fund_id"], book["code"])
        assert rules == fresh
        async with async_session_factory() as session:
            row = await session.get(FundFeeSchedule, book["fund_id"])
            assert row.parser_version == PARSER_VERSION
    finally:
        async with async_session_factory() as session:
            await session.execute(
                delete(FundFeeSchedule).where(FundFeeSchedule.fund_id == book["fund_id"])
            )
            await session.commit()
