"""资讯快讯采集：把几个公开行情快讯源归一化成统一的 NewsItem。

只同步标题、摘要、来源、原文链接与发布时间，**不保存正文**——
这些快讯有版权，全文搬运既有法律风险，也会让门户变成内容农场。
同步结果一律进草稿，由后台审核后再发布。

数据源全部来自项目已有的 AkShare（东方财富 / 财联社 / 同花顺），
单次调用 0.2–0.6 秒，无需新增依赖或凭据。
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from difflib import SequenceMatcher
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_SUMMARY_MAX = 400
_TITLE_MAX = 190

# 分类关键词：政策优先（"证监会发布上市公司监管规则"应归政策而不是公司）
_POLICY_WORDS = (
    "证监会",
    "央行",
    "人民银行",
    "国务院",
    "发改委",
    "财政部",
    "金融监管总局",
    "银保监",
    "上交所",
    "深交所",
    "北交所",
    "政策",
    "监管",
    "条例",
    "办法",
    "征求意见",
    "新规",
    "降准",
    "降息",
    "税率",
    "指导意见",
    "公开募集",
    "行业标准",
    "十五五",
    "规划",
    "批复",
    "处罚",
    "立案",
)
_COMPANY_WORDS = (
    "公告",
    "业绩",
    "财报",
    "营收",
    "净利",
    "回购",
    "增持",
    "减持",
    "中标",
    "董事长",
    "IPO",
    "上市",
    "获批",
    "股东",
    "财报",
    "预增",
    "预亏",
)
_MARKET_WORDS = (
    "沪指",
    "上证",
    "深证",
    "创业板",
    "A股",
    "大盘",
    "指数",
    "北向",
    "成交额",
    "板块",
    "涨跌",
    "美股",
    "港股",
    "金价",
    "油价",
    "汇率",
    "债券",
    "期货",
    "基金",
    "ETF",
    "收盘",
    "开盘",
    "市场",
    "资金",
    "利率",
)


# 相关性闸门：东财「全球财经快讯」里混着大量社会/国际新闻。
# 分两级：强词命中一条即收录；只有弱词时至少命中两个，
# 否则「乌克兰获 500 亿美元支持」这类只带一个"美元"的国际新闻也会混进来。
_STRONG_WORDS = (
    "证监会",
    "央行",
    "人民银行",
    "银保监",
    "金融监管总局",
    "上交所",
    "深交所",
    "北交所",
    "国务院",
    "发改委",
    "财政部",
    "基金",
    "ETF",
    "A股",
    "沪指",
    "上证",
    "深证",
    "创业板",
    "科创",
    "指数",
    "债券",
    "国债",
    "利率",
    "降准",
    "降息",
    "通胀",
    "GDP",
    "CPI",
    "PPI",
    "北向",
    "成交额",
    "板块",
    "政策",
    "新规",
    "条例",
    "办法",
    "征求意见",
    "公开募集",
    "证券",
    "银行",
    "财经",
    "金融",
    "两市",
    "收盘",
    "开盘",
    "股市",
    "债市",
    "港股",
    "美股",
    "保险",
    "期货",
    "期权",
    "IPO",
    "融资",
    "并购",
    "财报",
    "营收",
    "净利",
    "回购",
    "增持",
    "减持",
    "估值",
    "市值",
    "投顾",
    "投资者",
    "基金经理",
)
_WEAK_WORDS = (
    "股",
    "债",
    "汇",
    "税",
    "美元",
    "人民币",
    "经济",
    "消费",
    "出口",
    "进口",
    "能源",
    "原油",
    "黄金",
    "房地产",
    "财政",
    "企业",
    "产业",
    "涨",
    "跌",
    "交易",
    "资金",
    "利润",
    "价格",
    "产量",
    "订单",
    "业绩",
    "市场",
    "数据",
    "统计",
    "上市",
    "股东",
    "公告",
    "公司",
    "投资",
    "监管",
)


def is_relevant(title: str, summary: str) -> bool:
    """以标题判定相关性：强财经词命中一条，或弱财经词命中两条。

    刻意不看摘要：东财/财联社的摘要常是「多条要闻合集」，
    里面随便一句带"基金""市场"就会把整条国际新闻放进来。
    """
    text = title if len(title) >= 8 else f"{title} {summary[:60]}"
    if any(word in text for word in _STRONG_WORDS):
        return True
    return sum(1 for word in _WEAK_WORDS if word in text) >= 2


def classify(title: str, summary: str) -> str:
    """按关键词把快讯归到 policy / market / company，兜底 market。"""
    text = f"{title} {summary[:120]}"
    if any(word in text for word in _POLICY_WORDS):
        return "policy"
    if any(word in text for word in _COMPANY_WORDS):
        return "company"
    if any(word in text for word in _MARKET_WORDS):
        return "market"
    return "market"


@dataclass(frozen=True, slots=True)
class NewsItem:
    title: str
    summary: str
    url: str | None
    published_at: datetime | None
    source: str
    source_name: str
    category: str
    external_id: str


@dataclass(frozen=True, slots=True)
class _Source:
    key: str
    name: str
    fetch: Callable[[], Any]
    parse: Callable[[Any], list[NewsItem]]


def _clean(value: Any, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if limit else text


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = _clean(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _strip_title_prefix(summary: str, title: str) -> str:
    """东财快讯的摘要常以【标题】开头，去掉重复前缀。"""
    prefix = f"【{title}】"
    return summary[len(prefix) :].strip() if summary.startswith(prefix) else summary


def _fingerprint(source: str, title: str, published_at: datetime | None) -> str:
    """源 + 标题 + 时间做指纹：同一条快讯重复同步不会生成第二篇文章。"""
    stamp = published_at.isoformat(timespec="seconds") if published_at else ""
    raw = f"{source}|{title}|{stamp}".encode()
    return hashlib.sha1(raw).hexdigest()[:32]


def _make(
    *,
    source: str,
    source_name: str,
    title: str,
    summary: str,
    url: str | None,
    published_at: datetime | None,
) -> NewsItem | None:
    title = _clean(title, _TITLE_MAX)
    summary = _clean(_strip_title_prefix(summary, title), _SUMMARY_MAX)
    if len(title) < 6 or len(summary) < 8:
        return None
    if not is_relevant(title, summary):
        return None
    url = _clean(url, 500) or None
    if url and not url.startswith(("http://", "https://")):
        url = None
    return NewsItem(
        title=title,
        summary=summary,
        url=url,
        published_at=published_at,
        source=source,
        source_name=source_name,
        category=classify(title, summary),
        external_id=_fingerprint(source, title, published_at),
    )


def _parse_em(df: Any, *, source: str, name: str) -> list[NewsItem]:
    """东方财富快讯 / 财经早餐：标题·摘要·发布时间·链接。"""
    items: list[NewsItem] = []
    for row in df.itertuples(index=False):
        item = _make(
            source=source,
            source_name=name,
            title=_clean(getattr(row, "标题", "")),
            summary=_clean(getattr(row, "摘要", "")),
            url=_clean(getattr(row, "链接", "")),
            published_at=_parse_dt(getattr(row, "发布时间", None)),
        )
        if item:
            items.append(item)
    return items


def _parse_cls(df: Any) -> list[NewsItem]:
    """财联社电报：没有链接，标题有时为空，日期和时间分两列。"""
    items: list[NewsItem] = []
    for row in df.itertuples(index=False):
        content = _clean(getattr(row, "内容", ""))
        # "财联社11月7日电，..." 只是来源前缀，不属于正文
        content = re.sub(r"^财联社\d+月\d+日电[，,]?\s*", "", content)
        title = _clean(getattr(row, "标题", "")) or re.split(r"[。；!?]", content)[0][:_TITLE_MAX]

        day = getattr(row, "发布日期", None)
        moment = getattr(row, "发布时间", None)
        published_at: datetime | None
        if isinstance(day, date) and isinstance(moment, time):
            published_at = datetime.combine(day, moment)
        else:
            published_at = _parse_dt(f"{day} {moment}")

        item = _make(
            source="cls",
            source_name="财联社",
            title=title,
            summary=content,
            url=None,
            published_at=published_at,
        )
        if item:
            items.append(item)
    return items


def _parse_ths(df: Any) -> list[NewsItem]:
    """同花顺快讯：标题·内容·发布时间·链接。"""
    items: list[NewsItem] = []
    for row in df.itertuples(index=False):
        item = _make(
            source="ths",
            source_name="同花顺",
            title=_clean(getattr(row, "标题", "")),
            summary=_clean(getattr(row, "内容", "")),
            url=_clean(getattr(row, "链接", "")),
            published_at=_parse_dt(getattr(row, "发布时间", None)),
        )
        if item:
            items.append(item)
    return items


def _sources() -> tuple[_Source, ...]:
    """延迟 import akshare：纯函数单测不需要拉起这个大依赖。"""
    import akshare as ak

    return (
        _Source(
            "eastmoney",
            "东方财富",
            ak.stock_info_global_em,
            lambda df: _parse_em(df, source="eastmoney", name="东方财富"),
        ),
        _Source("cls", "财联社", ak.stock_info_global_cls, _parse_cls),
        _Source("ths", "同花顺", ak.stock_info_global_ths, _parse_ths),
        _Source(
            "cjzc",
            "东方财富·财经早餐",
            ak.stock_info_cjzc_em,
            lambda df: _parse_em(df, source="cjzc", name="东方财富·财经早餐"),
        ),
    )


def _title_key(title: str) -> str:
    """只保留中英文与数字，便于比较不同源的同一条快讯。"""
    return re.sub(r"[^\w\u4e00-\u9fff]", "", title).lower()


def collect_all(
    limit_per_source: int = 20, sources: tuple[_Source, ...] | None = None
) -> list[NewsItem]:
    """依次拉取各源，单源失败不影响其它；按时间倒序，做指纹 + 标题相似度去重。

    同一条伯克希尔快讯会被东财、同花顺、财联社同时推送，标题措辞略有差异；
    只用指纹去不掉，页面上就会出现三四张几乎一样的卡片。
    """
    specs = sources if sources is not None else _sources()
    collected: list[NewsItem] = []
    seen: set[str] = set()

    for spec in specs:
        try:
            df = spec.fetch()
            rows = spec.parse(df)[:limit_per_source]
            logger.info("[资讯] %s 取回 %d 条", spec.name, len(rows))
        except Exception as exc:  # 免费源偶发改版/超时，跳过即可
            logger.warning("[资讯] %s 获取失败: %s", spec.key, exc)
            continue

        for item in rows:
            if item.external_id in seen:
                continue
            seen.add(item.external_id)
            collected.append(item)

    collected.sort(key=lambda i: i.published_at or datetime.min, reverse=True)

    result: list[NewsItem] = []
    title_keys: list[str] = []
    for item in collected:
        key = _title_key(item.title)
        if any(SequenceMatcher(None, key, previous).ratio() >= 0.75 for previous in title_keys):
            continue
        title_keys.append(key)
        result.append(item)
    return result
