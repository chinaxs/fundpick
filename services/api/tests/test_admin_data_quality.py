"""Admin quality report identifies missing data and suggested collection mode."""

from uuid import uuid4

from sqlalchemy import delete, select

from app.db.session import async_session_factory
from app.models.fund import Fund
from app.models.fund_metric import FundMetric


async def test_data_quality_reports_missing_fund_data(client):
    username = f"quality_{uuid4().hex[:8]}"
    fund_code = f"{uuid4().int % 1_000_000:06d}"
    login = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    async with async_session_factory() as session:
        while await session.scalar(select(Fund.id).where(Fund.code == fund_code)):
            fund_code = f"{uuid4().int % 1_000_000:06d}"
        session.add(Fund(code=fund_code, name=username, type="stock"))
        await session.commit()

    try:
        response = await client.get(
            "/api/v1/admin/funds/data-quality",
            params={"keyword": fund_code, "page_size": 100},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        report = response.json()["data"]
        issue = next(row for row in report["items"] if row["code"] == fund_code)
        assert "缺少最新净值" in issue["fields"]
        assert "缺少 1 年收益指标" in issue["fields"]
        assert issue["suggested_mode"] == "snapshot"
        assert report["summary"]["affected_funds"] > 0
    finally:
        async with async_session_factory() as session:
            fund_id = await session.scalar(select(Fund.id).where(Fund.code == fund_code))
            if fund_id is not None:
                await session.execute(delete(FundMetric).where(FundMetric.fund_id == fund_id))
                await session.execute(delete(Fund).where(Fund.id == fund_id))
                await session.commit()
