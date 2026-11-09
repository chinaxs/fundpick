"""Batched Tencent stock snapshots. Keep upstream timestamp, never use fetch time as price time."""

import math
import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.trading_calendar import SHANGHAI

SOURCE = "腾讯证券行情"


@dataclass(frozen=True)
class StockQuote:
    code: str
    price: float | None
    change_pct: float | None
    quoted_at: datetime


def stock_symbol(code: str) -> str | None:
    if re.fullmatch(r"\d{5}", code):
        return "hk" + code
    if not re.fullmatch(r"\d{6}", code):
        return None
    if code.startswith("6"):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    if code.startswith(("4", "8", "92")):
        return "bj" + code
    return None


def number(value: str) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def parse_quotes(text: str, requested: dict[str, str]) -> dict[str, StockQuote]:
    result = {}
    for symbol, line in re.findall(r'v_([a-zA-Z0-9]+)="([^"\n]*)";', text):
        if symbol not in requested:
            continue
        parts = line.split("~")
        if len(parts) < 33 or parts[2] != requested[symbol]:
            continue
        moment = None
        for pattern in ("%Y%m%d%H%M%S", "%Y/%m/%d %H:%M:%S"):
            try:
                moment = datetime.strptime(parts[30], pattern).replace(tzinfo=SHANGHAI)
                break
            except ValueError:
                continue
        if moment is None:
            continue
        price = number(parts[3])
        result[requested[symbol]] = StockQuote(
            code=requested[symbol],
            price=price if price and price > 0 else None,
            change_pct=number(parts[32]) if price and price > 0 else None,
            quoted_at=moment,
        )
    return result


def fetch_stock_quotes(codes: list[str]) -> dict[str, StockQuote]:
    requested = {symbol: code for code in codes if (symbol := stock_symbol(code))}
    if not requested:
        return {}
    with httpx.Client(
        timeout=5, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}
    ) as client:
        response = client.get("https://qt.gtimg.cn/q=" + ",".join(requested))
        response.raise_for_status()
        return parse_quotes(response.content.decode("gb18030", errors="replace"), requested)
