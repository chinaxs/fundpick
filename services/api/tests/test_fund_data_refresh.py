"""Freshness, dividend-safe risk measures and timestamped stock quotes."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import delete, select

from app.datasources.akshare_source import AkShareProvider
from app.datasources.base import FundHolding as SourceHolding
from app.datasources.base import NavPoint
from app.datasources.stock_quotes import StockQuote, parse_quotes, stock_symbol
from app.db.session import async_session_factory
from app.models import Fund, FundDataCheck, FundHolding, FundMetric, FundNav
from app.schemas.fund import NavRange
from app.services import fund_data, stock_quotes
from app.services.fund import FundService
from app.services.fund_risk import calculate_risk
from app.trading_calendar import SHANGHAI
from scripts import sync_funds


@pytest.fixture
async def sample_fund():
    async with async_session_factory() as session:
        code = str(800000 + uuid4().int % 100000)
        while await session.scalar(select(Fund.id).where(Fund.code == code)):
            code = str(800000 + uuid4().int % 100000)
        fund = Fund(
            code=code,
            name="刷新验收基金",
            latest_nav=Decimal("1.2"),
            latest_nav_date=date(2026, 11, 6),
        )
        session.add(fund)
        await session.commit()
        fund_id = fund.id
    yield code, fund_id
    async with async_session_factory() as session:
        for model in (FundDataCheck, FundNav, FundMetric, FundHolding):
            await session.execute(delete(model).where(model.fund_id == fund_id))
        await session.execute(delete(Fund).where(Fund.id == fund_id))
        await session.commit()


async def test_existing_navs_refresh_to_latest_and_cache_attempt(monkeypatch, sample_fund):
    code, fund_id = sample_fund
    calls = []

    def history(requested):
        calls.append(requested)
        return [NavPoint(date(2026, 11, 5), 1.1, 1), NavPoint(date(2026, 11, 6), 1.2, 2)]

    monkeypatch.setattr(fund_data, "get_provider", lambda: SimpleNamespace(nav_history=history))
    async with async_session_factory() as session:
        session.add(FundNav(fund_id=fund_id, nav_date=date(2026, 11, 5), unit_nav=1.1))
        await session.commit()
        rows = await FundService(session).ensure_navs(code, NavRange.ALL)
        assert rows[-1].nav_date == date(2026, 11, 6)
        assert rows[-1].daily_return == 2
        assert calls == [code]
    async with async_session_factory() as session:
        rows = await FundService(session).ensure_navs(code, NavRange.ALL)
        assert rows[-1].unit_nav == 1.2
        assert calls == [code]


async def test_failed_refresh_keeps_history_and_official_snapshot(monkeypatch, sample_fund):
    code, fund_id = sample_fund
    calls = []

    def unavailable(code):
        calls.append(code)
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(fund_data, "get_provider", lambda: SimpleNamespace(nav_history=unavailable))
    async with async_session_factory() as session:
        session.add(
            FundNav(fund_id=fund_id, nav_date=date(2026, 11, 5), unit_nav=1.1, daily_return=1)
        )
        await session.commit()
        rows = await FundService(session).ensure_navs(code, NavRange.ALL)
        assert [(r.nav_date, r.unit_nav) for r in rows] == [
            (date(2026, 11, 5), 1.1),
            (date(2026, 11, 6), 1.2),
        ]
        assert rows[-1].daily_return is None
        stamp = await session.get(FundDataCheck, (fund_id, "navs"))
        assert stamp.succeeded is False
        await FundService(session).ensure_navs(code, NavRange.ALL)
        assert len(calls) == 1


async def test_holdings_refresh_even_when_quarter_already_cached(monkeypatch, sample_fund):
    code, fund_id = sample_fund
    monkeypatch.setattr(
        fund_data,
        "get_provider",
        lambda: SimpleNamespace(
            fund_holdings=lambda code, year: [
                SourceHolding("2026Q3", "300750", "宁德时代", 1, 10, 20, 0.8)
            ]
        ),
    )
    async with async_session_factory() as session:
        session.add(
            FundHolding(fund_id=fund_id, quarter="2026Q2", stock_code="300750", rank=1, ratio=9)
        )
        await session.commit()
        result = await FundService(session).holdings(code)
        assert result.quarter == "2026Q3"
        assert result.items[0].market_value == 0.8
        old = await FundService(session).holdings(code, "2026Q2")
        assert old.items[0].ratio == 9


def test_risk_uses_disclosed_returns_instead_of_distribution_drop():
    points = [
        NavPoint(
            date(2026, 10, 1) + timedelta(days=i), 0.5 if i >= 10 else 1, (-2 if i % 3 == 0 else 1)
        )
        for i in range(32)
    ]
    values, reason = calculate_risk(points, "1m", date(2020, 1, 1))
    assert reason is None
    assert values and values["max_drawdown"] < 10
    assert values["volatility"] > 0
    assert values["sharpe"] is not None


def test_risk_rejects_short_missing_or_constant_series():
    points = [NavPoint(date(2026, 10, 1) + timedelta(days=i), 1, 0) for i in range(32)]
    values, reason = calculate_risk(points, "1y", date(2026, 10, 1))
    assert values is None and "成立" in reason
    points[-1].daily_return = None
    assert calculate_risk(points, "1m")[0] is None
    points[-1].daily_return = 0
    values, reason = calculate_risk(points, "1m")
    assert values["volatility"] == 0 and values["sharpe"] is None


async def test_missing_one_year_row_is_selected_for_risk_sync(monkeypatch, sample_fund):
    code, fund_id = sample_fund
    monkeypatch.setattr(
        sync_funds,
        "get_provider",
        lambda: SimpleNamespace(name="test", risk_metrics=lambda code: []),
    )
    async with async_session_factory() as session:
        assert await sync_funds.sync_risks(session, limit=1, codes=[code]) == 1
        row = await session.scalar(
            select(FundMetric).where(FundMetric.fund_id == fund_id, FundMetric.period == "1y")
        )
        assert row.risk_nav_date == date(2026, 11, 6)


def test_quote_parser_preserves_zero_and_market_identity():
    fields = [""] * 34
    fields[2], fields[3], fields[30], fields[32] = "300750", "200", "20261109150000", "0.00"
    text = 'v_sz300750="' + "~".join(fields) + '";'
    parsed = parse_quotes(text, {"sz300750": "300750"})
    assert parsed["300750"].change_pct == 0
    assert parsed["300750"].quoted_at.isoformat() == "2026-11-09T15:00:00+08:00"
    assert parse_quotes(text, {"sh300750": "300750"}) == {}
    assert stock_symbol("300750") == "sz300750"
    assert stock_symbol("600000") == "sh600000"
    assert stock_symbol("00700") == "hk00700"
    assert stock_symbol("TSLA") is None


async def test_previous_day_quote_and_failure_keep_timestamp(monkeypatch):
    import asyncio

    stock_quotes._cache.clear()
    monkeypatch.setattr(stock_quotes, "_lock", asyncio.Lock())
    old = datetime.now(SHANGHAI) - timedelta(days=1)
    monkeypatch.setattr(
        stock_quotes,
        "fetch_stock_quotes",
        lambda codes: {"300750": StockQuote("300750", 200, 1.5, old)},
    )
    result = await stock_quotes.holding_quotes(["300750", "TSLA"])
    assert not result.items[0].is_today
    assert result.items[1].price is None
    stamp, value, _ = stock_quotes._cache["300750"]
    stock_quotes._cache["300750"] = (stamp - 100, value, False)

    def unavailable(codes):
        raise RuntimeError("offline")

    monkeypatch.setattr(stock_quotes, "fetch_stock_quotes", unavailable)
    result = await stock_quotes.holding_quotes(["300750"])
    assert result.items[0].quoted_at == old and result.items[0].degraded
    assert not result.items[0].is_today
    stock_quotes._cache.clear()


def test_holding_value_unit_conversion(monkeypatch):
    import app.datasources.akshare_source as source

    frame = pd.DataFrame(
        [
            {
                "季度": "2026年2季度股票投资明细",
                "股票代码": "300750",
                "股票名称": "宁德时代",
                "占净值比例": 10,
                "持股数": 20,
                "持仓市值": 7690.95,
            }
        ]
    )
    monkeypatch.setattr(source.ak, "fund_portfolio_hold_em", lambda **kwargs: frame)
    result = AkShareProvider().fund_holdings("025196", "2026")
    assert result[0].market_value == 0.7691


async def test_risks_derive_from_full_history_without_overwriting_return(sample_fund):
    code, fund_id = sample_fund
    async with async_session_factory() as session:
        fund = await session.get(Fund, fund_id)
        fund.inception_date = date(2026, 9, 1)
        session.add(FundMetric(fund_id=fund_id, period="1m", return_rate=12.34))
        session.add_all(
            [
                FundNav(
                    fund_id=fund_id,
                    nav_date=date(2026, 9, 1) + timedelta(days=i),
                    unit_nav=1,
                    daily_return=1 if i % 2 else -0.5,
                )
                for i in range(67)
            ]
        )
        await session.commit()
        metrics = {m.period: m for m in await FundService(session).metrics(code)}
        assert metrics["1m"].return_rate == 12.34
        assert metrics["1m"].risk_coverage == 3
        assert metrics["1m"].risk_nav_date == date(2026, 11, 6)
        assert "252" in metrics["1m"].risk_source
        assert metrics["1y"].risk_coverage == 0
        assert "成立时间不足" in metrics["1y"].risk_reason
