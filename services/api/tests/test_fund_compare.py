"""基金对比与份额类别。

用开发库里的真实代码：000003 / 000004 是同一只债基的 A/C 份额，
正好验证"同产品不同份额"不会被当成两个不同标的。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.fund_share_class import share_class_label, split_share_class

BASE = "/api/v1/portal/funds"


def test_share_class_split() -> None:
    assert split_share_class("华夏成长混合A") == ("华夏成长混合", "A")
    assert split_share_class("华夏成长混合A类") == ("华夏成长混合", "A")
    assert split_share_class("某某基金（C）") == ("某某基金", "C")
    assert split_share_class("国泰中证全指证券公司ETF联接A") == (
        "国泰中证全指证券公司ETF联接",
        "A",
    )
    # 英文后缀不误判
    assert split_share_class("沪深300ETF") == ("沪深300ETF", None)
    assert split_share_class("易方达蓝筹精选混合") == ("易方达蓝筹精选混合", None)
    assert split_share_class(None) == ("", None)


def test_share_class_label() -> None:
    assert share_class_label("中海可转债债券A") == "A 类"
    assert share_class_label("易方达蓝筹精选混合") is None


async def test_compare_two_share_classes(client: AsyncClient) -> None:
    resp = await client.get(f"{BASE}/compare", params={"codes": "000003,000004"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert [item["code"] for item in data["items"]] == ["000003", "000004"]
    first, second = data["items"]
    assert first["share_class"] == "A"
    assert second["share_class"] == "C"
    assert first["base_name"] == second["base_name"]
    assert data["periods"] == ["3m", "6m", "1y", "3y"]
    assert len(first["periods"]) == 4
    assert "费率" in data["note"]


async def test_compare_requires_two_codes(client: AsyncClient) -> None:
    single = await client.get(f"{BASE}/compare", params={"codes": "000003"})
    assert single.status_code in (400, 422)

    too_many = await client.get(f"{BASE}/compare", params={"codes": "000001,000002,000003,000004"})
    assert too_many.status_code in (400, 422)


async def test_compare_unknown_code(client: AsyncClient) -> None:
    resp = await client.get(f"{BASE}/compare", params={"codes": "000003,999999"})
    assert resp.status_code == 404


async def test_compare_dedupes_codes(client: AsyncClient) -> None:
    resp = await client.get(f"{BASE}/compare", params={"codes": "000003,000003"})
    assert resp.status_code in (400, 422)


async def test_fund_detail_exposes_share_class(client: AsyncClient) -> None:
    detail = await client.get(f"{BASE}/000003")
    assert detail.status_code == 200, detail.text
    body = detail.json()["data"]
    assert body["share_class"] == "A"
    assert body["base_name"]

    plain = await client.get(f"{BASE}/000001")
    assert plain.status_code == 200
    # 000001 是后端收费份额的旧命名，未必带字母类别；只要字段存在即可
    assert "share_class" in plain.json()["data"]


@pytest.mark.parametrize("code", ["000003", "000004"])
async def test_list_items_carry_share_class(client: AsyncClient, code: str) -> None:
    resp = await client.get(BASE, params={"keyword": code, "page_size": 5})
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert items
    assert items[0]["share_class"] in {"A", "C", None}
