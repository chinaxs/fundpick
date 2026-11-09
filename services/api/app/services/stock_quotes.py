"""Short-lived stock quote cache, isolated from quarterly position disclosures."""

import asyncio
from collections import OrderedDict
from datetime import datetime
from time import monotonic

from app.core.logging import get_logger
from app.datasources.stock_quotes import SOURCE, StockQuote, fetch_stock_quotes, stock_symbol
from app.schemas.fund import HoldingQuoteRead, HoldingQuotesResult
from app.trading_calendar import SHANGHAI

logger = get_logger(__name__)
_cache: OrderedDict[str, tuple[float, StockQuote | None, bool]] = OrderedDict()
_lock = asyncio.Lock()


async def holding_quotes(codes: list[str]) -> HoldingQuotesResult:
    selected = list(dict.fromkeys(codes))[:10]
    async with _lock:
        missing = [
            code
            for code in selected
            if stock_symbol(code)
            and (
                code not in _cache
                or monotonic() - _cache[code][0] >= (20 if _cache[code][2] else 60)
            )
        ]
        if missing:
            try:
                received = await asyncio.wait_for(asyncio.to_thread(fetch_stock_quotes, missing), 6)
                for code in missing:
                    value = received.get(code)
                    old = _cache.get(code)
                    _cache[code] = (monotonic(), value or (old[1] if old else None), value is None)
                    _cache.move_to_end(code)
            except Exception as error:
                logger.info("重仓股行情暂不可用: %s", type(error).__name__)
                for code in missing:
                    old = _cache.get(code)
                    _cache[code] = (monotonic(), old[1] if old else None, True)
                    _cache.move_to_end(code)
            while len(_cache) > 512:
                _cache.popitem(last=False)
        now = datetime.now(SHANGHAI)
        items = []
        for code in selected:
            cached = _cache.get(code)
            value = cached[1] if cached else None
            supported = stock_symbol(code) is not None
            today = bool(value and value.quoted_at.date() == now.date())
            items.append(
                HoldingQuoteRead(
                    stock_code=code,
                    price=value.price if value else None,
                    change_pct=value.change_pct if value else None,
                    quoted_at=value.quoted_at if value else None,
                    is_today=today,
                    degraded=bool(not value or (cached and cached[2])),
                    source=SOURCE if value else None,
                    message="暂不支持该市场"
                    if not supported
                    else "行情暂不可用"
                    if not value
                    else "上游暂不可用，保留最近行情"
                    if cached and cached[2]
                    else None
                    if today
                    else "非今日行情",
                )
            )
        return HoldingQuotesResult(items=items, fetched_at=now)
