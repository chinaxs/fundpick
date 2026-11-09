"""门户 - 市场指数行情（公开接口）。

与大屏行情软件不同，这里的定位是"辅助判断市场环境"：
首页顶部一根指数条 + 大盘页的走势卡片 + 单指数的分时详情。

三种取数方式，各有各的适用场景：

- `/indices`：一次拿全部（列表页、首屏 SSR）；
- `/indices/{code}` / `/indices/{code}/intraday`：单指数详情，前端按需轮询；
- `/indices/stream`：SSE 推送，全站指数条用一条连接接住所有更新。

数据源为东方财富公开行情，延迟约数秒到十几秒；
非交易时段返回最近收盘值，用 `trade_date` 标明这是哪天的数据。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import RequestIdDep
from app.schemas.common import ApiResponse
from app.schemas.market import (
    IndexCandlesData,
    IndexIntradayData,
    IndexQuoteRead,
    IndexTrendsData,
    MarketIndicesData,
)
from app.services.market_index import MarketIndexService, get_quote_stream

router = APIRouter(prefix="/market", tags=["门户 · 行情"])


def format_quote_event(snapshot: MarketIndicesData) -> str:
    """SSE 帧格式：事件名固定 quotes，data 是完整快照。

    单独抽出来是为了能直接测格式——SSE 是无限流，
    用 httpx 的 ASGI 传输测试时整个响应会被缓冲，读不到中间帧。
    """
    return f"event: quotes\ndata: {snapshot.model_dump_json()}\n\n"


@router.get(
    "/indices",
    summary="核心指数实时行情",
    response_model=ApiResponse[MarketIndicesData],
)
async def indices(request_id: RequestIdDep) -> ApiResponse[MarketIndicesData]:
    """上证、深证、创业板、科创50、沪深300、中证500/1000、北证50。

    服务端有 5 秒短缓存；如果页面需要持续更新，优先用
    `/indices/stream` 订阅推送，而不是自己写轮询。
    """
    data = await MarketIndexService().quotes()
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/indices/trends",
    summary="核心指数日线走势",
    response_model=ApiResponse[IndexTrendsData],
)
async def index_trends(
    request_id: RequestIdDep,
    days: Annotated[int, Query(ge=5, le=250, description="回看交易日数量")] = 60,
) -> ApiResponse[IndexTrendsData]:
    """各指数最近 N 个交易日的收盘序列，供迷你走势图使用。

    日线数据一天只变一次，服务端缓存 5 分钟。
    """
    data = await MarketIndexService().trends(days)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/indices/stream",
    summary="核心指数行情推送（SSE）",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "SSE 流。每条消息为 `event: quotes`，data 是 MarketIndicesData 的 JSON，"
                "推送间隔随交易状态变化（盘中 5 秒、其余 30 秒）。"
            ),
        }
    },
)
async def index_stream(request: Request) -> StreamingResponse:
    """一条长连接持续接收全部指数快照。

    为什么不是 WebSocket：行情是只读的单向流，SSE 走普通 HTTP，
    断线由浏览器自动重连，不需要协议升级、心跳帧和双向状态机。

    为什么不需要 Redis：推送内容来自公开行情源，是幂等快照。
    多 worker 部署时每个进程各自刷新同一份数据，结果一致；
    只有在"订阅某个业务事件"时才需要跨进程广播。
    """

    async def events() -> AsyncIterator[str]:
        # retry 告诉浏览器断线后 5 秒重连；首帧由 subscribe() 立刻给出，
        # 页面不用等一个推送周期才有数据。
        yield "retry: 5000\n\n"
        async for snapshot in get_quote_stream().subscribe():
            if await request.is_disconnected():
                break
            yield format_quote_event(snapshot)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Nginx 默认会缓冲响应，关掉它，否则 SSE 会攒一批才吐出来
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/indices/{code}",
    summary="单个指数实时快照",
    response_model=ApiResponse[IndexQuoteRead],
)
async def index_quote(request_id: RequestIdDep, code: str) -> ApiResponse[IndexQuoteRead]:
    """详情页头部用。代码必须在跟踪清单内，否则 404。"""
    try:
        data = await MarketIndexService().quote(code)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未跟踪的指数代码：{code}",
        ) from None

    if data is None:
        # 代码合法但行情源没给数据：这是上游故障，不是用户请求错了
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="行情源暂时不可用",
        )
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/indices/{code}/intraday",
    summary="单个指数当日分时",
    response_model=ApiResponse[IndexIntradayData],
)
async def index_intraday(request_id: RequestIdDep, code: str) -> ApiResponse[IndexIntradayData]:
    """分钟级分时序列，含昨收（画基准线、算每个点的涨跌幅）。

    盘中缓存 20 秒，休市后 120 秒；上游失败时返回 200 + 空序列，
    前端显示"分时暂不可用"，不影响页面其它部分。
    """
    try:
        data = await MarketIndexService().intraday(code)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未跟踪的指数代码：{code}",
        ) from None
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/indices/{code}/candles",
    summary="单个指数日 K",
    response_model=ApiResponse[IndexCandlesData],
)
async def index_candles(
    request_id: RequestIdDep,
    code: str,
    days: Annotated[int, Query(ge=20, le=2000, description="返回的交易日数量")] = 250,
) -> ApiResponse[IndexCandlesData]:
    """日 K 序列（升序），供蜡烛图使用。

    服务端缓存 5 分钟；一次向数据源取全量历史再按窗口截取，
    不同窗口的请求可以共用同一份缓存。
    """
    try:
        data = await MarketIndexService().candles(code, days)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未跟踪的指数代码：{code}",
        ) from None
    return ApiResponse(data=data, request_id=request_id)
