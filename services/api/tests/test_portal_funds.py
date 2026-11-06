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


async def test_sector_filter_options(client: AsyncClient) -> None:
    """筛选项字典返回板块及其数量，通用词不会被误判成板块。"""
    resp = await client.get("/api/v1/portal/funds/filters")
    assert resp.status_code == 200
    sectors = {s["value"]: s for s in resp.json()["data"]["sectors"]}
    assert "new_energy" in sectors and "semiconductor" in sectors
    assert all(s["count"] > 0 for s in sectors.values())
    # 全称里"证券投资基金"曾让全库被误判为金融板块
    assert sectors.get("finance", {}).get("count", 0) < 1000


async def test_sector_filter_narrows_result(client: AsyncClient) -> None:
    """按板块筛选后，结果集里的每只基金都属于该板块。"""
    resp = await client.get(
        "/api/v1/portal/funds", params={"sector": "semiconductor", "page_size": 5}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] > 0
    assert all(item["sector"] == "semiconductor" for item in data["items"])


async def test_detect_sector_ignores_generic_full_name() -> None:
    from app.fund_sectors import detect_sector

    assert detect_sector("华夏成长混合", "华夏成长证券投资基金") is None
    assert detect_sector("易方达消费行业股票", "易方达消费行业股票型证券投资基金") == "consumer"
    assert (
        detect_sector("国联安中证半导体ETF联接A", tracking_index="中证全指半导体产品与设备指数")
        == "semiconductor"
    )
