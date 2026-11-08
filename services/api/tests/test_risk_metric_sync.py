"""风险指标以最新净值日期为基准，刷新并暴露来源与覆盖数。"""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from app.datasources.base import RiskMetric
from app.db.session import async_session_factory
from app.models.fund import Fund
from app.models.fund_metric import FundMetric
from app.services.fund import FundService
from scripts import sync_funds


async def test_risk_metrics_refresh_when_nav_baseline_changes(monkeypatch, client):
    code = f"{uuid4().int % 1_000_000:06d}"
    first_date = date(2026, 11, 6)
    async with async_session_factory() as session:
        while await session.scalar(select(Fund.id).where(Fund.code == code)):
            code = f"{uuid4().int % 1_000_000:06d}"
        fund = Fund(code=code, name="风险指标刷新测试", latest_nav_date=first_date)
        session.add(fund)
        await session.flush()
        fund_id = fund.id
        session.add(
            FundMetric(
                fund_id=fund_id,
                period="1y",
                nav_date=first_date,
                return_rate=12,
                sharpe=0.8,
                risk_nav_date=first_date - timedelta(days=1),
                risk_source="旧来源",
            )
        )
        await session.commit()

    class Provider:
        name = "test-provider"

        def __init__(self):
            self.calls = []

        def risk_metrics(self, requested_code):
            self.calls.append(requested_code)
            return [
                RiskMetric(
                    period="1y",
                    volatility=18.2,
                    sharpe=1.1,
                    max_drawdown=21.5,
                    source="雪球基金分析",
                )
            ]

    provider = Provider()
    monkeypatch.setattr(sync_funds, "get_provider", lambda: provider)
    try:
        async with async_session_factory() as session:
            assert await sync_funds.sync_risks(session, limit=10, codes=[code]) == 1
        assert provider.calls == [code]

        async with async_session_factory() as session:
            metrics = {row.period: row for row in await FundService(session).metrics(code)}
            one_year = metrics["1y"]
            assert one_year.return_rate == 12
            assert one_year.risk_nav_date == first_date
            assert one_year.risk_source == "雪球基金分析"
            assert one_year.risk_coverage == 3
            assert one_year.risk_stale is False
            assert metrics["3y"].risk_coverage == 0
            assert metrics["3y"].risk_nav_date == first_date
        response = await client.get(f"/api/v1/portal/funds/{code}/metrics")
        assert response.status_code == 200, response.text
        api_metrics = {row["period"]: row for row in response.json()["data"]}
        assert api_metrics["1y"]["risk_nav_date"] == str(first_date)
        assert api_metrics["1y"]["risk_source"] == "雪球基金分析"
        assert api_metrics["1y"]["risk_coverage"] == 3
        assert api_metrics["1y"]["risk_stale"] is False

        async with async_session_factory() as session:
            assert await sync_funds.sync_risks(session, limit=10, codes=[code]) == 0
        assert provider.calls == [code]

        async with async_session_factory() as session:
            fund = await session.scalar(select(Fund).where(Fund.id == fund_id))
            fund.latest_nav_date = first_date + timedelta(days=1)
            await session.commit()
        response = await client.get(f"/api/v1/portal/funds/{code}/metrics")
        assert response.status_code == 200, response.text
        stale = {row["period"]: row for row in response.json()["data"]}
        assert stale["1y"]["risk_stale"] is True
        async with async_session_factory() as session:
            assert await sync_funds.sync_risks(session, limit=10, codes=[code]) == 1
        assert provider.calls == [code, code]

        async with async_session_factory() as session:
            metrics = {row.period: row for row in await FundService(session).metrics(code)}
            assert metrics["1y"].risk_nav_date == first_date + timedelta(days=1)
            assert metrics["1y"].risk_stale is False
    finally:
        async with async_session_factory() as session:
            fund_ids = select(Fund.id).where(Fund.code == code)
            await session.execute(delete(FundMetric).where(FundMetric.fund_id.in_(fund_ids)))
            await session.execute(delete(Fund).where(Fund.code == code))
            await session.commit()
