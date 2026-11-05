"""门户基金接口测试：详情费率语义与持仓查询。"""

import pytest
from httpx import AsyncClient

# 已在采集时验证过真实数据的基金：管理费 1.2 / 托管费 0.2
FEE_FIXED_FUND = "021180"


async def test_holdings_shape(client: AsyncClient) -> None:
    """持仓接口：返回季度列表 + 按占比降序的明细。"""
    resp = await client.get(f"/api/v1/portal/funds/{FEE_FIXED_FUND}/holdings")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["quarters"], "至少有一个披露季度"
    assert data["quarter"] in data["quarters"]
    assert data["items"], "021180 应有持仓明细"

    ratios = [i["ratio"] for i in data["items"] if i["rank"] and i["rank"] <= 10]
    assert ratios == sorted(ratios, reverse=True), "前十大应按占比降序"

    if data["total_ratio"] is not None:
        assert 0 < data["total_ratio"] <= 100


async def test_holdings_unknown_quarter_falls_back(client: AsyncClient) -> None:
    """指定不存在的季度时回退到最新披露季度，而不是报错。"""
    resp = await client.get(
        f"/api/v1/portal/funds/{FEE_FIXED_FUND}/holdings",
        params={"quarter": "2001Q1"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["quarter"] == data["quarters"][0]


async def test_holdings_unknown_fund_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/portal/funds/99999999/holdings")
    assert resp.status_code == 404


async def test_detail_fee_is_real_not_zero(client: AsyncClient) -> None:
    """详情里的费率必须是真实管理费（曾误把申购费 0 写进 management_fee）。"""
    resp = await client.get(f"/api/v1/portal/funds/{FEE_FIXED_FUND}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fee_rate"] == 1.2, "021180 真实管理费应为 1.2（申购费为 0 不能冒充）"
    assert data["custody_fee"] == 0.2
