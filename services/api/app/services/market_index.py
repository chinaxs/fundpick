"""市场指数行情服务。

三层保护，避免免费行情源被首页流量打穿：

1. **短缓存**：快照 5 秒、走势 5 分钟，期间所有访客共用一份结果；
2. **单飞（request coalescing）**：缓存过期瞬间若同时来 50 个请求，
   只发起一次上游请求，其余等同一个结果；
3. **降级**：上游偶发失败时返回上一次的缓存（标注数据时间），
   大盘行情不该把首页整页拖挂。

推送（SSE）走的是另一条路：进程内一个后台任务按 `push_seconds` 刷新，
所有连接从同一个队列取数据——连接数再涨，上游请求数也不变。
多 worker 部署时每个进程各跑一份；行情是幂等的公开快照，
不需要跨进程一致，因此不必引入 Redis 广播。

缓存是进程内的。多 worker 部署时每个 worker 各存一份，
总请求量 = 访客数 / (TTL × worker 数)，对免费源依然可控。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import suppress
from datetime import date, datetime, time
from time import monotonic
from typing import Any, cast

from app.core.logging import get_logger
from app.datasources import get_provider
from app.datasources.base import IndexQuote
from app.market_indices import (
    INDEX_BY_CODE,
    MARKET_TZ,
    STATUS_LABELS,
    TRACKED_INDICES,
    TrackedIndex,
    calendar_known,
    calendar_trade_date,
    market_status,
)
from app.schemas.market import (
    IndexCandlePoint,
    IndexCandlesData,
    IndexIntradayData,
    IndexMinutePoint,
    IndexQuoteRead,
    IndexTrendItem,
    IndexTrendsData,
    MarketIndicesData,
    TrendPoint,
)

logger = get_logger(__name__)

QUOTE_TTL = 5.0  # 快照：行情源本身延迟就有十几秒，缓存再短没有意义
TREND_TTL = 300.0  # 日线走势：一天只变一次，5 分钟足够新鲜
TRADE_DATE_TTL = 600.0
INTRADAY_TTL_TRADING = 20.0  # 分时一天只加一个点，但要跟上最新一分钟
INTRADAY_TTL_IDLE = 120.0  # 休市后分时不再变化
CANDLE_TTL = 300.0  # 日 K：一天只变一次，5 分钟足够
UPSTREAM_TIMEOUT = 8.0  # 上游卡住时的兜底，避免整页 SSR 等在这里

PUSH_SECONDS_TRADING = 5  # 盘中推送间隔；也是 SSE 的心跳（空闲 30 秒，低于常见的 60 秒超时）
PUSH_SECONDS_IDLE = 30


# key -> (写入时刻 monotonic, 值)
_cache: dict[str, tuple[float, Any]] = {}
# key -> 上游数据的取得时间 / 是否正在用旧缓存（降级）
_cache_written: dict[str, datetime] = {}
_cache_degraded: dict[str, bool] = {}


def cache_meta(key: str) -> tuple[datetime | None, float | None, bool]:
    """返回（数据取得时间、缓存年龄秒数、是否降级）。

    为什么把"响应时间"和"数据时间"分开：`as_of` 每次请求都会变，
    拿它当数据时间会让旧缓存看起来像刚更新的行情。
    """
    written = _cache_written.get(key)
    if written is None:
        return None, None, _cache_degraded.get(key, False)
    age = (datetime.now(MARKET_TZ) - written).total_seconds()
    return written, round(age, 1), _cache_degraded.get(key, False)


# key -> (所属事件循环, 进行中的任务)。带 loop 是为了兼容测试里每例新建循环
_inflight: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Task[Any]]] = {}


async def _coalesced[T](key: str, ttl: float, factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """带缓存与单飞地执行 factory()。

    factory 必须是无参可等待函数。上游异常时回退到过期缓存（若有）。
    """
    hit = _cache.get(key)
    if hit is not None and monotonic() - hit[0] < ttl:
        return cast("T", hit[1])

    loop = asyncio.get_running_loop()
    running = _inflight.get(key)
    if running is not None and running[0] is loop and not running[1].done():
        return cast("T", await running[1])

    task: asyncio.Task[T] = loop.create_task(factory())
    _inflight[key] = (loop, task)
    try:
        value = await task
    except Exception as exc:
        if hit is not None:
            age = monotonic() - hit[0]
            logger.warning("指数数据 %s 刷新失败，回退到 %.0fs 前的缓存: %s", key, age, exc)
            _cache_degraded[key] = True
            return cast("T", hit[1])
        raise
    finally:
        current = _inflight.get(key)
        if current is not None and current[1] is task:
            _inflight.pop(key, None)

    _cache[key] = (monotonic(), value)
    _cache_written[key] = datetime.now(MARKET_TZ)
    _cache_degraded[key] = False
    return value


async def _run_upstream[T](fn: Callable[[], T]) -> T:
    """把同步的阻塞调用丢进线程池，并给一个超时上限。

    免费行情源偶发卡住（连接建不起来又不报错），没有超时会一直占着
    一次 SSR 请求；wait_for 至少能把请求放出来，返回空数据由上层降级。
    """
    return await asyncio.wait_for(asyncio.to_thread(fn), timeout=UPSTREAM_TIMEOUT)


def _to_read(item: IndexQuote, tracked: TrackedIndex) -> IndexQuoteRead:
    """把数据源快照映射成对外的展示结构。"""
    change_pct = item.change_pct
    if change_pct is None and item.change is not None and item.prev_close:
        change_pct = item.change / item.prev_close * 100
    return IndexQuoteRead(
        code=item.code,
        name=item.name or tracked.name,
        group=tracked.group,
        price=item.price,
        change=item.change,
        change_pct=change_pct,
        open=item.open,
        high=item.high,
        low=item.low,
        prev_close=item.prev_close,
        amplitude=item.amplitude,
        volume=item.volume,
        amount=item.amount,
    )


class MarketIndexService:
    """指数行情读取。无数据库依赖，纯外部数据 + 缓存。"""

    async def quotes(self) -> MarketIndicesData:
        status = market_status()
        as_of = datetime.now(MARKET_TZ)

        try:
            raw = await _coalesced(
                "index-quotes",
                QUOTE_TTL,
                lambda: _run_upstream(get_provider().index_quotes),
            )
            trade_date = await _coalesced(
                "index-trade-date",
                TRADE_DATE_TTL,
                lambda: _run_upstream(self._fetch_trade_date),
            )
        except Exception as exc:
            logger.warning("指数实时行情获取失败: %s", exc)
            return MarketIndicesData(
                items=[],
                market_status=status,
                status_label=STATUS_LABELS[status],
                trade_date=calendar_trade_date(),
                as_of=as_of,
                fetched_at=None,
                data_as_of=None,
                cache_age_seconds=None,
                calendar_known=calendar_known(),
                degraded=True,
                degraded_reason=f"上游行情不可用：{type(exc).__name__}",
                push_seconds=(PUSH_SECONDS_TRADING if status == "trading" else PUSH_SECONDS_IDLE),
            )

        fetched, cache_age, degraded = cache_meta("index-quotes")
        by_code = {item.code: item for item in raw}
        items = [
            _to_read(by_code[tracked.code], tracked)
            for tracked in TRACKED_INDICES
            if tracked.code in by_code
        ]
        missing = [t.code for t in TRACKED_INDICES if t.code not in by_code]
        if missing:
            logger.warning("行情源缺少指数: %s", ",".join(missing))

        return MarketIndicesData(
            items=items,
            market_status=status,
            status_label=STATUS_LABELS[status],
            trade_date=trade_date or calendar_trade_date(),
            as_of=as_of,
            fetched_at=fetched,
            # 上游快照没有时间戳：不拿抓取时间冒充行情时间，宁可留空
            data_as_of=None,
            cache_age_seconds=cache_age,
            calendar_known=calendar_known(),
            degraded=degraded,
            degraded_reason="上游刷新失败，展示上次缓存" if degraded else None,
            push_seconds=(PUSH_SECONDS_TRADING if status == "trading" else PUSH_SECONDS_IDLE),
        )

    async def quote(self, code: str) -> IndexQuoteRead | None:
        """单个指数快照；代码不在跟踪清单里时抛 KeyError。"""
        if code not in INDEX_BY_CODE:
            raise KeyError(code)
        data = await self.quotes()
        return next((item for item in data.items if item.code == code), None)

    async def candles(self, code: str, days: int = 250) -> IndexCandlesData:
        """日 K 序列（升序），最多返回 `days` 个交易日。"""
        tracked = INDEX_BY_CODE.get(code)
        if tracked is None:
            raise KeyError(code)

        as_of = datetime.now(MARKET_TZ)
        try:
            raw = await _coalesced(
                f"index-candles:{code}",
                CANDLE_TTL,
                lambda: _run_upstream(lambda: get_provider().index_candles(tracked.symbol)),
            )
        except Exception as exc:
            logger.warning("指数日 K 获取失败 %s: %s", code, exc)
            raw = []

        window = raw[-days:] if days > 0 else raw
        fetched, cache_age, degraded = cache_meta(f"index-candles:{code}")
        last_bar = window[-1] if window else None
        data_as_of = (
            datetime.combine(last_bar.trade_date, time(15, 0), tzinfo=MARKET_TZ)
            if last_bar is not None
            else None
        )
        return IndexCandlesData(
            code=code,
            name=tracked.name,
            days=len(window),
            points=[
                IndexCandlePoint(
                    trade_date=bar.trade_date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    amount=bar.amount,
                )
                for bar in window
            ],
            as_of=as_of,
            fetched_at=fetched,
            data_as_of=data_as_of,
            cache_age_seconds=cache_age,
            degraded=degraded or last_bar is None,
            degraded_reason=(
                "上游日 K 刷新失败，展示缓存"
                if degraded
                else ("暂无日 K 数据" if last_bar is None else None)
            ),
            calendar_known=calendar_known(),
        )

    async def intraday(self, code: str) -> IndexIntradayData:
        """当日分时序列（1 分钟粒度）。"""
        tracked = INDEX_BY_CODE.get(code)
        if tracked is None:
            raise KeyError(code)

        status = market_status()
        as_of = datetime.now(MARKET_TZ)
        ttl = INTRADAY_TTL_TRADING if status == "trading" else INTRADAY_TTL_IDLE

        try:
            raw = await _coalesced(
                f"index-intraday:{code}",
                ttl,
                lambda: _run_upstream(lambda: get_provider().index_intraday(tracked.symbol)),
            )
        except Exception as exc:
            logger.warning("指数分时获取失败 %s: %s", code, exc)
            raw = None

        points = (
            [
                IndexMinutePoint(
                    time=bar.moment.strftime("%H:%M"),
                    price=bar.price,
                    avg_price=bar.avg_price,
                    volume=bar.volume,
                    amount=bar.amount,
                )
                for bar in raw.points
            ]
            if raw
            else []
        )

        fetched, cache_age, degraded = cache_meta(f"index-intraday:{code}")
        last_point = raw.points[-1].moment if raw and raw.points else None
        return IndexIntradayData(
            code=code,
            name=(raw.name if raw and raw.name else tracked.name),
            prev_close=raw.prev_close if raw else None,
            points=points,
            trade_date=(
                raw.points[-1].moment.date() if raw and raw.points else calendar_trade_date()
            ),
            market_status=status,
            status_label=STATUS_LABELS[status],
            as_of=as_of,
            fetched_at=fetched,
            data_as_of=last_point,
            cache_age_seconds=cache_age,
            degraded=degraded or not points,
            degraded_reason=(
                "上游分时刷新失败，展示缓存"
                if degraded
                else ("暂无分时数据" if not points else None)
            ),
            calendar_known=calendar_known(),
            refresh_seconds=20 if status == "trading" else 120,
        )

    async def trends(self, days: int = 60) -> IndexTrendsData:
        as_of = datetime.now(MARKET_TZ)
        try:
            series = await _coalesced(
                f"index-trends:{days}",
                TREND_TTL,
                lambda: self._fetch_all_trends(days),
            )
        except Exception as exc:
            logger.warning("指数走势获取失败: %s", exc)
            series = []

        return IndexTrendsData(days=days, items=series, as_of=as_of)

    # ---- 内部：同步阻塞部分放进线程池 ----

    @staticmethod
    def _fetch_trade_date() -> date | None:
        """用第一条指数的日线末点作为"行情所属交易日"。"""
        provider = get_provider()
        points = provider.index_daily(TRACKED_INDICES[0].symbol)
        return points[-1].trade_date if points else None

    async def _fetch_all_trends(self, days: int) -> list[IndexTrendItem]:
        """并发拉取各指数日线（单条约 0.3 秒，串行会到 3 秒以上）。"""

        async def one(tracked: TrackedIndex) -> IndexTrendItem:
            try:
                points = await asyncio.to_thread(get_provider().index_daily, tracked.symbol)
            except Exception as exc:  # 单个指数失败不影响其它
                logger.debug("指数日线 %s 获取失败: %s", tracked.code, exc)
                return IndexTrendItem(code=tracked.code, name=tracked.name)
            window = points[-days:]
            change_pct = None
            if len(window) >= 2 and window[0].close:
                change_pct = (window[-1].close - window[0].close) / window[0].close * 100
            return IndexTrendItem(
                code=tracked.code,
                name=tracked.name,
                points=[TrendPoint(trade_date=p.trade_date, close=p.close) for p in window],
                change_pct=change_pct,
            )

        return list(await asyncio.gather(*(one(t) for t in TRACKED_INDICES)))


class QuoteStream:
    """进程内的行情广播（SSE 的数据源）。

    关键取舍：**不是每个连接各自去拉上游**。1 万个 SSE 连接如果有 1 万个
    协程各自调一次行情接口，免费源立刻就挂了。这里只有一个后台任务按
    5 秒/30 秒的节奏刷新，把结果塞进订阅者的队列——连接数涨，上游请求数不变。

    队列容量是 1：客户端慢（或页面在后台被节流）时只保留最新的快照，
    丢掉的中间帧对"看当前点位"没有意义，堆积反而会撑爆内存。
    """

    def __init__(self, service: MarketIndexService | None = None) -> None:
        self._service = service or MarketIndexService()
        self._subscribers: set[asyncio.Queue[MarketIndicesData]] = set()
        self._task: asyncio.Task[None] | None = None
        self._task_loop: asyncio.AbstractEventLoop | None = None
        self._latest: MarketIndicesData | None = None

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def subscribe(self) -> AsyncIterator[MarketIndicesData]:
        """订阅行情。先立刻给一帧（缓存里就有），再等着后续推送。"""
        queue: asyncio.Queue[MarketIndicesData] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        self._ensure_task()
        try:
            snapshot = self._latest
            if snapshot is None:
                snapshot = await self._service.quotes()
                self._latest = snapshot
            yield snapshot

            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)
            if not self._subscribers:
                self._stop_task()

    def _ensure_task(self) -> None:
        loop = asyncio.get_running_loop()
        if self._task is not None and not self._task.done() and self._task_loop is loop:
            return
        self._task_loop = loop
        self._task = loop.create_task(self._run())

    def _stop_task(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        """后台刷新循环。取消时安静退出，异常只记日志、不杀死循环。"""
        try:
            while True:
                try:
                    snapshot = await self._service.quotes()
                    self._latest = snapshot
                    self._publish(snapshot)
                    interval = (
                        PUSH_SECONDS_TRADING
                        if snapshot.market_status == "trading"
                        else PUSH_SECONDS_IDLE
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # 上游抖动不该让推送停掉
                    logger.warning("行情推送刷新失败: %s", exc)
                    interval = PUSH_SECONDS_IDLE
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

    def _publish(self, snapshot: MarketIndicesData) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                with suppress(asyncio.QueueEmpty):  # 竞态：别的协程刚取走
                    queue.get_nowait()  # 丢掉旧帧，保留最新
            with suppress(asyncio.QueueFull):  # 并发写入兜底
                queue.put_nowait(snapshot)


_stream: QuoteStream | None = None


def get_quote_stream() -> QuoteStream:
    """全局唯一的广播实例：SSE 连接共享同一个后台刷新任务。"""
    global _stream
    if _stream is None:
        _stream = QuoteStream()
    return _stream


def reset_quote_stream() -> None:
    """测试用：丢弃旧实例（旧事件循环里的任务随循环关闭一起消失）。"""
    global _stream
    if _stream is not None:
        _stream._stop_task()
    _stream = None
