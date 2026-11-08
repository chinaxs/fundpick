"""东方财富分时（分钟内）行情直连。

为什么不用 AkShare 的分时封装：
`index_zh_a_hist_min_em` 内部按 17 个分页依次拉取，实测单次 22 秒；
而东财 push2his 的 trends2 接口一次就能返回当日全部分钟点（约 0.2 秒）。
详情页的"分时图"是点开就要看的，不能用 20 秒的接口。

这里只做"取数 + 解析"，不掺业务规则；缓存与降级在 service 层。
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.core.logging import get_logger
from app.datasources.base import IndexIntraday, IndexMinuteBar
from app.market_indices import MARKET_TZ

logger = get_logger(__name__)

TRENDS_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"

# 字段含义：f51 时间、f52 开、f53 收、f54 高、f55 低、f56 成交量、f57 成交额、f58 均价
_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    # 停牌/无成交时东财会给 0 或 "-"，0 对指数分时是有效值（极少见），照原样保留
    return number


def fetch_intraday(secid: str, ndays: int = 1) -> IndexIntraday | None:
    """取指数的分钟级分时序列。

    Args:
        secid: 东财市场号 + 代码，如 `1.000001`（沪）、`0.399001`（深/北）。
        ndays: 返回最近几个交易日；1 表示当日分时。

    Returns:
        分时序列；上游无数据（代码不存在、接口返回空）时返回 None。
    """
    params: dict[str, str | int] = {
        "secid": secid,
        "fields1": _FIELDS1,
        "fields2": _FIELDS2,
        "ndays": ndays,
        "iscr": 0,
    }
    try:
        with httpx.Client(timeout=6.0, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(TRENDS_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("东财分时接口失败 %s: %s", secid, exc)
        raise

    data = payload.get("data")
    if not data:
        return None

    bars: list[IndexMinuteBar] = []
    for line in data.get("trends") or []:
        parts = str(line).split(",")
        if len(parts) < 8:
            continue
        try:
            # 上游给的是北京时间且不带偏移；不补时区会被异地浏览器按本机时区解释，
            # 展示时间与"是否收盘"判断都会偏。
            moment = datetime.strptime(parts[0], "%Y-%m-%d %H:%M").replace(tzinfo=MARKET_TZ)
        except ValueError:
            continue
        price = _to_float(parts[2])
        if price is None:
            continue
        bars.append(
            IndexMinuteBar(
                moment=moment,
                price=price,
                avg_price=_to_float(parts[7]),
                volume=_to_float(parts[5]),
                amount=_to_float(parts[6]),
            )
        )

    if not bars:
        return None

    return IndexIntraday(
        name=str(data.get("name") or ""),
        prev_close=_to_float(data.get("preClose")),
        points=bars,
    )
