"""市场指数行情测试：交易时段判定、清单过滤、缓存与降级。

行情源不做真实网络请求——用假 provider 固定输入，避免测试受交易时段影响。
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.datasources.base import (
    IndexCandle,
    IndexDailyPoint,
    IndexIntraday,
    IndexMinuteBar,
    IndexQuote,
)
from app.market_indices import MARKET_TZ, TRACKED_INDICES, market_status
from app.services import market_index as service_module


class _FakeProvider:
    """按需构造指数快照，调用次数用于验证缓存是否生效。"""

    def __init__(
        self,
        quotes: list[IndexQuote],
        daily: list[IndexDailyPoint],
        intraday: IndexIntraday | None = None,
        candles: list[IndexCandle] | None = None,
    ) -> None:
        self._quotes = quotes
        self._daily = daily
        self._intraday = intraday
        self._candles = candles or []
        self.quote_calls = 0
        self.daily_calls = 0
        self.intraday_calls = 0
        self.candle_calls = 0

    def index_quotes(self) -> list[IndexQuote]:
        self.quote_calls += 1
        return self._quotes

    def index_daily(self, symbol: str) -> list[IndexDailyPoint]:
        self.daily_calls += 1
        return self._daily

    def index_intraday(self, symbol: str, ndays: int = 1) -> IndexIntraday | None:
        self.intraday_calls += 1
        return self._intraday

    def index_candles(self, symbol: str) -> list[IndexCandle]:
        self.candle_calls += 1
        return self._candles


def _quotes(count: int | None = None) -> list[IndexQuote]:
    """构造清单内全部指数（外加一个不在清单里的指数）。"""
    tracked = TRACKED_INDICES[:count] if count else TRACKED_INDICES
    items = [
        IndexQuote(
            code=t.code,
            name=t.name,
            price=3000.0,
            change=12.5,
            change_pct=0.42,
            open=2980.0,
            high=3010.0,
            low=2975.0,
            prev_close=2987.5,
            amplitude=1.17,
            volume=1_000_000.0,
            amount=1.2e11,
        )
        for t in tracked
    ]
    # 行情源会返回 40+ 个指数，服务端必须只保留清单内的
    items.append(IndexQuote(code="000012", name="国债指数", price=232.0))
    return items


def _daily(days: int = 100) -> list[IndexDailyPoint]:
    start = date(2026, 1, 1)
    return [
        IndexDailyPoint(trade_date=start + timedelta(days=i), close=3000.0 + i) for i in range(days)
    ]


def _intraday() -> IndexIntraday:
    start = datetime(2026, 11, 6, 9, 30, tzinfo=MARKET_TZ)
    return IndexIntraday(
        name="上证指数",
        prev_close=2990.0,
        points=[
            IndexMinuteBar(
                moment=start + timedelta(minutes=i),
                price=3000.0 + i,
                avg_price=2999.0 + i * 0.8,
                volume=1000.0,
                amount=1.5e8,
            )
            for i in range(5)
        ],
    )


def _candles(days: int = 300) -> list[IndexCandle]:
    start = date(2025, 1, 1)
    return [
        IndexCandle(
            trade_date=start + timedelta(days=i),
            open=3000.0 + i,
            high=3010.0 + i,
            low=2990.0 + i,
            close=3005.0 + i,
            volume=1e6,
            amount=1.2e11,
        )
        for i in range(days)
    ]


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    service_module._cache.clear()
    service_module._inflight.clear()
    service_module._cache_written.clear()
    service_module._cache_degraded.clear()
    service_module.reset_quote_stream()


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> _FakeProvider:
    fake = _FakeProvider(_quotes(), _daily(), _intraday(), _candles())
    monkeypatch.setattr(service_module, "get_provider", lambda: fake)
    return fake


# ---------------------------------------------------------------- 交易时段


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        ("2026-11-06 09:00", "pre_open"),
        ("2026-11-06 09:30", "trading"),
        ("2026-11-06 11:29", "trading"),
        ("2026-11-06 11:30", "lunch_break"),
        ("2026-11-06 12:59", "lunch_break"),
        ("2026-11-06 13:00", "trading"),
        ("2026-11-06 14:59", "trading"),
        ("2026-11-06 15:00", "closed"),
        ("2026-11-06 22:00", "closed"),
        ("2026-11-07 10:00", "closed"),  # 周六
    ],
)
def test_market_status_boundaries(moment: str, expected: str) -> None:
    """边界必须精确：11:30 已经休市，15:00 已经收盘，周末一律收盘。"""
    now = datetime.strptime(moment, "%Y-%m-%d %H:%M").replace(tzinfo=MARKET_TZ)
    assert market_status(now) == expected


# ---------------------------------------------------------------- 接口


async def test_indices_only_tracked_and_ordered(
    client: AsyncClient, provider: _FakeProvider
) -> None:
    resp = await client.get("/api/v1/portal/market/indices")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    codes = [item["code"] for item in data["items"]]
    assert codes == [t.code for t in TRACKED_INDICES], "只返回清单内指数且按清单顺序"
    assert "000012" not in codes, "清单外的指数不应透出"
    assert data["trade_date"] == _daily()[-1].trade_date.isoformat()
    assert data["market_status"] in {"pre_open", "trading", "lunch_break", "closed"}
    assert data["status_label"]
    assert data["refresh_seconds"] > 0


async def test_indices_fall_back_to_computed_pct(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """上游缺涨跌幅时用涨跌额/昨收补算，避免前端显示"—"。"""
    fake = _FakeProvider(
        [IndexQuote(code="000001", name="上证指数", price=3012.5, change=25.0, prev_close=2987.5)],
        _daily(),
    )
    monkeypatch.setattr(service_module, "get_provider", lambda: fake)

    resp = await client.get("/api/v1/portal/market/indices")
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["change_pct"] == pytest.approx(25.0 / 2987.5 * 100, rel=1e-3)


async def test_indices_cache_shared_between_requests(
    client: AsyncClient, provider: _FakeProvider
) -> None:
    """15 秒缓存内重复请求不应再打上游。"""
    await client.get("/api/v1/portal/market/indices")
    await client.get("/api/v1/portal/market/indices")
    assert provider.quote_calls == 1


async def test_indices_degrade_when_source_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """行情源不可用时返回 200 + 空列表，而不是把首页拖成 500。"""

    class _Broken:
        def index_quotes(self) -> Any:
            raise RuntimeError("upstream down")

        def index_daily(self, symbol: str) -> Any:
            raise RuntimeError("upstream down")

    monkeypatch.setattr(service_module, "get_provider", lambda: _Broken())

    resp = await client.get("/api/v1/portal/market/indices")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["market_status"] in {"pre_open", "trading", "lunch_break", "closed"}


async def test_trends_window_and_change(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/trends", params={"days": 30})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["days"] == 30
    assert len(data["items"]) == len(TRACKED_INDICES)
    for item in data["items"]:
        assert len(item["points"]) == 30, "只返回请求窗口内的交易日"
        assert item["points"][0]["close"] < item["points"][-1]["close"]
        assert item["change_pct"] is not None and item["change_pct"] > 0


async def test_trends_days_out_of_range(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/trends", params={"days": 400})
    assert resp.status_code == 422


# ---------------------------------------------------------------- 单指数详情


async def test_single_quote(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/000001")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["code"] == "000001"
    assert data["name"] == "上证指数"
    assert data["group"] == "沪市"
    assert data["prev_close"] == 2987.5


async def test_single_quote_unknown_code(client: AsyncClient, provider: _FakeProvider) -> None:
    """清单外的代码要明确 404，而不是返回空对象让前端显示空白页。"""
    resp = await client.get("/api/v1/portal/market/indices/999999")
    assert resp.status_code == 404


async def test_single_quote_source_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """代码合法但上游没数据：503，前端可以提示"行情源不可用"。"""

    class _Broken:
        def index_quotes(self) -> Any:
            raise RuntimeError("upstream down")

        def index_daily(self, symbol: str) -> Any:
            raise RuntimeError("upstream down")

        def index_intraday(self, symbol: str, ndays: int = 1) -> Any:
            raise RuntimeError("upstream down")

    monkeypatch.setattr(service_module, "get_provider", lambda: _Broken())

    resp = await client.get("/api/v1/portal/market/indices/000001")
    assert resp.status_code == 503


async def test_intraday_shape(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/000001/intraday")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["code"] == "000001"
    assert data["name"] == "上证指数"
    assert data["prev_close"] == 2990.0
    assert data["trade_date"] == "2026-11-06"
    assert len(data["points"]) == 5
    assert data["points"][0]["time"] == "09:30"
    assert data["points"][0]["price"] == 3000.0
    assert data["points"][0]["avg_price"] is not None
    assert data["refresh_seconds"] > 0


async def test_intraday_cached(client: AsyncClient, provider: _FakeProvider) -> None:
    await client.get("/api/v1/portal/market/indices/000001/intraday")
    await client.get("/api/v1/portal/market/indices/000001/intraday")
    assert provider.intraday_calls == 1, "分时缓存期内不应重复打上游"


async def test_intraday_degrades_to_empty(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """上游分时失败时返回空序列，页面其余部分照常可用。"""

    class _Broken:
        def index_quotes(self) -> Any:
            return _quotes()

        def index_daily(self, symbol: str) -> Any:
            return _daily()

        def index_intraday(self, *, symbol: str, ndays: int = 1) -> Any:
            raise RuntimeError("upstream down")

    monkeypatch.setattr(service_module, "get_provider", lambda: _Broken())

    resp = await client.get("/api/v1/portal/market/indices/000001/intraday")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["points"] == []
    assert data["prev_close"] is None


async def test_intraday_unknown_code(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/999999/intraday")
    assert resp.status_code == 404


# ---------------------------------------------------------------- SSE 推送


async def test_stream_first_frame_and_release(provider: _FakeProvider) -> None:
    """连上立刻给一帧；断开后退订，订阅者归零。"""
    stream = service_module.get_quote_stream()
    generator = stream.subscribe()

    snapshot = await asyncio.wait_for(generator.__anext__(), timeout=2)
    assert len(snapshot.items) == len(TRACKED_INDICES)
    assert stream.subscriber_count == 1

    await generator.aclose()

    for _ in range(40):
        if stream.subscriber_count == 0:
            break
        await asyncio.sleep(0.05)
    assert stream.subscriber_count == 0
    assert stream._task is None, "没有订阅者时后台刷新任务必须停掉"


async def test_stream_format_is_valid_sse(provider: _FakeProvider) -> None:
    """帧格式：event 行 + data 行 + 空行，data 能被前端直接 JSON.parse。"""
    from app.api.v1.portal.market import format_quote_event

    stream = service_module.get_quote_stream()
    generator = stream.subscribe()
    snapshot = await asyncio.wait_for(generator.__anext__(), timeout=2)
    await generator.aclose()

    frame = format_quote_event(snapshot)
    assert frame.startswith("event: quotes\n")
    assert frame.endswith("\n\n"), "SSE 以空行结束一帧"

    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line[len("data: ") :])
    assert len(payload["items"]) == len(TRACKED_INDICES)
    assert payload["push_seconds"] > 0


# ---------------------------------------------------------------- 日 K


async def test_candles_window(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/000001/candles", params={"days": 60})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["code"] == "000001"
    assert data["name"] == "上证指数"
    assert len(data["points"]) == 60, "只返回窗口内的交易日"
    assert data["days"] == 60

    first = data["points"][0]
    assert set(first) >= {"trade_date", "open", "high", "low", "close", "volume", "amount"}
    # 升序：最后一条是最新交易日
    assert data["points"][0]["trade_date"] < data["points"][-1]["trade_date"]


async def test_candles_cached_across_windows(client: AsyncClient, provider: _FakeProvider) -> None:
    """不同 days 共用一次上游请求：缓存的是全量历史。"""
    await client.get("/api/v1/portal/market/indices/000001/candles", params={"days": 60})
    await client.get("/api/v1/portal/market/indices/000001/candles", params={"days": 120})
    assert provider.candle_calls == 1


async def test_candles_unknown_code(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/999999/candles")
    assert resp.status_code == 404


async def test_candles_days_out_of_range(client: AsyncClient, provider: _FakeProvider) -> None:
    resp = await client.get("/api/v1/portal/market/indices/000001/candles", params={"days": 5})
    assert resp.status_code == 422


async def test_candles_degrade_to_empty(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Broken:
        def index_quotes(self) -> Any:
            return _quotes()

        def index_daily(self, symbol: str) -> Any:
            return _daily()

        def index_intraday(self, symbol: str, ndays: int = 1) -> Any:
            return _intraday()

        def index_candles(self, symbol: str) -> Any:
            raise RuntimeError("upstream down")

    monkeypatch.setattr(service_module, "get_provider", lambda: _Broken())

    resp = await client.get("/api/v1/portal/market/indices/000001/candles")
    assert resp.status_code == 200
    assert resp.json()["data"]["points"] == []


# ---------------------------------------------------------------- 数据时间与降级


async def test_quotes_separate_fetch_time_from_data_time(provider: _FakeProvider) -> None:
    data = await service_module.MarketIndexService().quotes()
    assert data.degraded is False
    assert data.degraded_reason is None
    # 快照本身没有时间戳：抓取时间不能冒充行情时间
    assert data.fetched_at is not None
    assert data.data_as_of is None
    assert data.cache_age_seconds is not None
    assert data.cache_age_seconds >= 0
    assert data.calendar_known is True
    # trade_date 必须有值：上游没给时用本地日历兜底
    assert data.trade_date is not None


async def test_candles_report_last_bar_time(provider: _FakeProvider) -> None:
    data = await service_module.MarketIndexService().candles("000001", days=5)
    assert data.points
    assert data.fetched_at is not None
    # 原始行情时间取最后一根日 K 的收盘时刻，而不是抓取时刻
    assert data.data_as_of is not None
    assert data.data_as_of.date() == data.points[-1].trade_date
    assert data.data_as_of.hour == 15
    assert data.degraded is False


async def test_candles_without_data_is_degraded(
    provider: _FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "index_candles", lambda symbol: [])
    data = await service_module.MarketIndexService().candles("000001", days=5)
    assert data.points == []
    assert data.data_as_of is None
    assert data.degraded is True
    assert data.degraded_reason


async def test_intraday_uses_last_point_time(provider: _FakeProvider) -> None:
    data = await service_module.MarketIndexService().intraday("000001")
    assert data.points
    assert data.data_as_of is not None
    assert data.data_as_of.strftime("%H:%M") == data.points[-1].time


def test_calendar_known_flags_unknown_year() -> None:
    from app.market_indices import calendar_known

    assert calendar_known(date(2026, 11, 6)) is True
    assert calendar_known(date(2027, 3, 1)) is False


async def test_upstream_failure_marks_degraded_and_keeps_items(
    provider: _FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = service_module.MarketIndexService()
    first = await service.quotes()
    assert first.items

    def boom() -> list[IndexQuote]:
        raise RuntimeError("upstream down")

    monkeypatch.setattr(provider, "index_quotes", boom)
    # 把缓存改成"已过期"，强制走一次上游
    cached = service_module._cache["index-quotes"]
    service_module._cache["index-quotes"] = (cached[0] - 600, cached[1])

    second = await service.quotes()
    assert second.degraded is True
    assert second.degraded_reason
    assert len(second.items) == len(first.items)
    assert second.cache_age_seconds is not None


def test_market_status_uses_holiday_calendar() -> None:
    assert market_status(datetime(2026, 10, 1, 10, 0, tzinfo=MARKET_TZ)) == "closed"
    assert market_status(datetime(2026, 11, 6, 10, 0, tzinfo=MARKET_TZ)) == "trading"
    # 日历未覆盖的年份不猜测：按星期兜底，不能让页面报错
    assert market_status(datetime(2027, 3, 1, 10, 0, tzinfo=MARKET_TZ)) == "trading"
    assert market_status(datetime(2027, 3, 6, 10, 0, tzinfo=MARKET_TZ)) == "closed"


def test_latest_trading_day_and_unknown_year() -> None:
    from app.trading_calendar import latest_trading_day, trading_day_or_none

    # 周日 → 最近的周五
    assert latest_trading_day(date(2026, 11, 8)) == date(2026, 11, 6)
    # 国庆假期（10-01 至 10-07 休市）→ 节前最后一个交易日 09-30
    assert latest_trading_day(date(2026, 10, 3)) == date(2026, 9, 30)
    # 未核对年份返回 None，由调用方决定降级方式
    assert trading_day_or_none(date(2027, 3, 1)) is None
    assert latest_trading_day(date(2027, 3, 1)) is None


async def test_intraday_payload_carries_shanghai_offset(provider: _FakeProvider) -> None:
    """分时的原始行情时间必须带 +08:00，否则异地浏览器会按本机时区解释。"""
    data = await service_module.MarketIndexService().intraday("000001")
    assert data.data_as_of is not None
    assert data.data_as_of.utcoffset() == timedelta(hours=8)
    assert data.calendar_known is True
