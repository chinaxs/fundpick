"""资讯采集与门户分类：纯函数 + 接口回归。

采集器不联网：用假 DataFrame 固定输入，避免免费源抖动导致测试不稳定。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.session import async_session_factory
from app.models.article import Article, ArticleStatus
from app.news_sources import (
    NewsItem,
    _fingerprint,
    _parse_cls,
    _parse_dt,
    _parse_em,
    _Source,
    classify,
    collect_all,
    is_relevant,
)


def _em_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "标题": "央行发布新规稳定市场预期",
                "摘要": (
                    "【央行发布新规稳定市场预期】央行今日发布新规，"
                    "涉及基金销售适当性管理与市场流动性。"
                ),
                "发布时间": "2026-11-07 10:00:00",
                "链接": "https://example.com/news/1",
            }
        ]
    )


def _cls_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "标题": "",
                "内容": "财联社11月7日电，央行开展逆回购操作，市场流动性保持充裕。后续视情况调整。",
                "发布日期": date(2026, 11, 7),
                "发布时间": time(10, 30, 0),
            }
        ]
    )


# ---------------------------------------------------------------- 纯函数


def test_parse_dt_accepts_string_and_native() -> None:
    assert _parse_dt("2026-11-07 10:00:00") == datetime(2026, 11, 7, 10, 0, 0)
    assert _parse_dt("2026-11-07") == datetime(2026, 11, 7)
    assert _parse_dt(date(2026, 11, 7)) == datetime(2026, 11, 7)
    assert _parse_dt("不是时间") is None


def test_parse_em_strips_duplicate_title_prefix() -> None:
    items = _parse_em(_em_frame(), source="eastmoney", name="东方财富")
    assert len(items) == 1
    item = items[0]
    assert not item.summary.startswith("【")
    assert item.category == "policy", "含央行/新规，应归政策"
    assert item.url == "https://example.com/news/1"
    assert item.source_name == "东方财富"


def test_parse_cls_builds_title_when_missing() -> None:
    items = _parse_cls(_cls_frame())
    assert len(items) == 1
    item = items[0]
    assert item.title.startswith("央行开展逆回购操作")
    assert item.url is None, "财联社电报没有原文链接"
    assert item.published_at == datetime(2026, 11, 7, 10, 30, 0)
    assert item.source == "cls"


def test_fingerprint_is_stable_and_source_scoped() -> None:
    moment = datetime(2026, 11, 7, 10, 0, 0)
    first = _fingerprint("cls", "央行开展逆回购", moment)
    assert first == _fingerprint("cls", "央行开展逆回购", moment)
    assert first != _fingerprint("ths", "央行开展逆回购", moment)
    assert first != _fingerprint("cls", "另一条快讯", moment)


def test_classify_priority_and_fallback() -> None:
    assert classify("证监会发布上市公司监管规则", "涉及基金销售") == "policy"
    assert classify("某公司三季度净利润大增", "营收同比增长") == "company"
    assert classify("沪指收涨 1%", "两市成交额放大") == "market"
    assert classify("一则无关快讯", "没有财经词汇的普通描述") == "market"


def test_relevance_gate_filters_off_topic() -> None:
    assert is_relevant("央行下调存款准备金率", "释放长期资金约 5000 亿元")
    assert not is_relevant("也门胡塞武装称萨那周边遭空袭", "当地居民已撤离该区域")


def test_collect_all_skips_failed_source_and_dedupes() -> None:
    good = _Source(
        "eastmoney",
        "东方财富",
        _em_frame,
        lambda df: _parse_em(df, source="eastmoney", name="东方财富"),
    )
    duplicate = _Source(
        "eastmoney",
        "东方财富",
        _em_frame,
        lambda df: _parse_em(df, source="eastmoney", name="东方财富"),
    )
    broken = _Source(
        "broken",
        "坏源",
        lambda: (_ for _ in ()).throw(RuntimeError("upstream down")),
        lambda df: [],
    )

    items = collect_all(10, sources=(good, duplicate, broken))
    assert len(items) == 1, "同一指纹只保留一条，单源失败不影响其它"
    assert isinstance(items[0], NewsItem)


# ---------------------------------------------------------------- 接口


async def _seed(
    session: object, *, category: str, status: ArticleStatus, origin: str = "manual"
) -> Article:
    slug = f"test-news-{uuid.uuid4().hex[:10]}"
    article = Article(
        title=f"测试资讯 {category} {slug}",
        slug=slug,
        summary="央行发布新规，市场流动性改善，基金销售适当性管理调整。",
        content="原创正文" if origin == "manual" else None,
        status=status,
        published_at=datetime.now() - timedelta(days=1),
        category=category,
        origin=origin,
        source="cls" if origin == "sync" else None,
        source_name="财联社" if origin == "sync" else None,
        source_url="https://example.com/original" if origin == "sync" else None,
    )
    session.add(article)  # type: ignore[attr-defined]
    await session.commit()  # type: ignore[attr-defined]
    await session.refresh(article)  # type: ignore[attr-defined]
    return article


@pytest.fixture
async def seeded_articles() -> list[Article]:
    ids: list[int] = []
    async with async_session_factory() as session:
        for category, status, origin in [
            ("policy", ArticleStatus.PUBLISHED, "sync"),
            ("market", ArticleStatus.PUBLISHED, "manual"),
            ("company", ArticleStatus.DRAFT, "sync"),
        ]:
            article = await _seed(session, category=category, status=status, origin=origin)
            ids.append(article.id)
    yield ids
    async with async_session_factory() as session:
        await session.execute(delete(Article).where(Article.id.in_(ids)))
        await session.commit()


async def test_portal_category_filter(client: AsyncClient, seeded_articles: list[int]) -> None:
    resp = await client.get("/api/v1/portal/articles", params={"category": "policy"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] >= 1
    assert all(item["category"] == "policy" for item in data["items"])
    assert all(item["origin"] == "sync" for item in data["items"])


async def test_portal_article_exposes_source(
    client: AsyncClient, seeded_articles: list[int]
) -> None:
    # 库里可能已有真实发布的政策资讯，别假定第一条就是本用例种的种子数据
    listed = await client.get(
        "/api/v1/portal/articles", params={"category": "policy", "page_size": 50}
    )
    seeded = [
        item for item in listed.json()["data"]["items"] if item["slug"].startswith("test-news-")
    ]
    assert seeded, "种子文章应出现在政策分类里"
    slug = seeded[0]["slug"]

    resp = await client.get(f"/api/v1/portal/articles/{slug}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["source"] == "cls"
    assert data["source_name"] == "财联社"
    assert data["source_url"] == "https://example.com/original"
    assert data["origin"] == "sync"


async def test_draft_never_leaks_to_portal(client: AsyncClient, seeded_articles: list[int]) -> None:
    resp = await client.get("/api/v1/portal/articles", params={"page_size": 50})
    slugs = [item["slug"] for item in resp.json()["data"]["items"]]
    assert not any(slug.startswith("test-news-") and "company" in slug for slug in slugs)


async def test_invalid_category_rejected(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/portal/articles", params={"category": "whatever"})
    assert resp.status_code == 422


def test_collect_all_dedupes_similar_titles_across_sources() -> None:
    """同一条快讯被两家源用略不同的标题推送时，只保留一条。"""

    def frame(title: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "标题": title,
                    "摘要": "央行开展逆回购操作，银行体系流动性保持合理充裕。",
                    "发布时间": "2026-11-07 10:00:00",
                    "链接": "https://example.com/news/2",
                }
            ]
        )

    first = _Source(
        "eastmoney",
        "东方财富",
        lambda: frame("央行开展5000亿元逆回购操作维护流动性"),
        lambda df: _parse_em(df, source="eastmoney", name="东方财富"),
    )
    second = _Source(
        "ths",
        "同花顺",
        lambda: frame("央行开展5000亿元逆回购操作以维护流动性"),
        lambda df: _parse_em(df, source="ths", name="同花顺"),
    )

    items = collect_all(10, sources=(first, second))
    assert len(items) == 1
