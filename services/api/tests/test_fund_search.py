"""基金模糊搜索：关键词归一（拼音/首字母/板块）与接口行为。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.fund_search import pinyin_index, search_tokens, sector_code_for

# ---------------------------------------------------------------- 纯函数


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("华夏成长混合", ("huaxiachengzhanghunhe", "hxczhh")),
        ("易方达沪深300ETF联接A", ("yifangdahushen300etflianjiea", "yfdhs300etflja")),
        ("南方中证500ETF", ("nanfangzhongzheng500etf", "nfzz500etf")),
    ],
)
def test_pinyin_index(name: str, expected: tuple[str, str]) -> None:
    """拼音列只保留小写字母和数字，括号等符号一律去掉。"""
    assert pinyin_index(name) == expected


def test_pinyin_index_handles_empty() -> None:
    assert pinyin_index("") == ("", "")


def test_search_tokens_splits_and_dedupes() -> None:
    assert search_tokens("  华夏   混合 华夏 ") == ["华夏", "混合"]


def test_search_tokens_limits_count() -> None:
    assert len(search_tokens("a b c d e f")) == 4


def test_search_tokens_blank() -> None:
    assert search_tokens("   ") == []
    assert search_tokens(None) == []


def test_sector_code_for() -> None:
    assert sector_code_for("新能源") == "new_energy"
    assert sector_code_for("不存在的板块") is None


# ---------------------------------------------------------------- 接口


async def _total(client: AsyncClient, keyword: str) -> int:
    resp = await client.get("/api/v1/portal/funds", params={"keyword": keyword, "page_size": 1})
    assert resp.status_code == 200, resp.text
    return int(resp.json()["data"]["total"])


async def test_search_by_code(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/portal/funds", params={"keyword": "000001", "page_size": 3})
    codes = [item["code"] for item in resp.json()["data"]["items"]]
    assert "000001" in codes


async def test_search_by_name(client: AsyncClient) -> None:
    total = await _total(client, "华夏成长")
    assert total > 0


async def test_search_by_pinyin_initials(client: AsyncClient) -> None:
    """hxcz -> 华夏成长：库里没有这两个字母，全靠回填的首字母列。"""
    assert await _total(client, "hxcz") > 0


async def test_search_by_full_pinyin(client: AsyncClient) -> None:
    assert await _total(client, "huaxia") > 100


async def test_search_multiple_tokens_are_and(client: AsyncClient) -> None:
    """空格分隔是"且"：多加一个词只会收窄结果。"""
    single = await _total(client, "华夏")
    both = await _total(client, "华夏 混合")
    assert both > 0
    assert both < single


async def test_search_by_company(client: AsyncClient) -> None:
    """基金名里不一定含公司名，公司是独立的一列。"""
    assert await _total(client, "易方达") > 100


async def test_search_by_sector_label(client: AsyncClient) -> None:
    """中文板块名映射成板块 key，名里没"半导体"也能搜到。"""
    assert await _total(client, "半导体") > 50


async def test_search_unknown_keyword(client: AsyncClient) -> None:
    assert await _total(client, "zzzz不存在的基金zzzz") == 0


async def test_search_blank_keyword_is_no_filter(client: AsyncClient) -> None:
    """全是空格时不做过滤，返回全量。"""
    everything = await _total(client, " ")
    assert everything > 1000
