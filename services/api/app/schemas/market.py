"""市场指数行情（大盘）响应模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class IndexQuoteRead(BaseModel):
    """单个指数的实时快照。"""

    code: str = Field(description="指数代码，如 000001")
    name: str = Field(description="指数名称，如 上证指数")
    group: str = Field(description="展示分组：沪市/深市/成长/宽基/北交所")
    price: float | None = Field(default=None, description="最新点位")
    change: float | None = Field(default=None, description="涨跌点数")
    change_pct: float | None = Field(default=None, description="涨跌幅（%）")
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    amplitude: float | None = Field(default=None, description="振幅（%）")
    volume: float | None = Field(default=None, description="成交量（手）")
    amount: float | None = Field(default=None, description="成交额（元）")


class MarketIndicesData(BaseModel):
    """指数列表 + 数据时间。

    行情源本身有数秒到十几秒延迟，因此不承诺"逐笔实时"，
    但要明确告诉前端"这是什么时候的数据"，避免把收盘价当盘中价。
    """

    items: list[IndexQuoteRead] = Field(default_factory=list)
    market_status: str = Field(description="pre_open/trading/lunch_break/closed")
    status_label: str = Field(description="状态中文文案")
    trade_date: date | None = Field(default=None, description="行情所属交易日")
    as_of: datetime = Field(description="服务端本次响应的时间")
    fetched_at: datetime | None = Field(
        default=None, description="本次数据从上游抓取的时间；降级时可能是几分钟前"
    )
    data_as_of: datetime | None = Field(
        default=None,
        description="原始行情时间（如分时最后一个点、日 K 最后交易日）；上游未提供时为 null",
    )
    cache_age_seconds: float | None = Field(
        default=None, description="距最近一次成功抓取过去了多少秒"
    )
    calendar_known: bool = Field(
        default=True, description="交易日历是否覆盖当前年份；false 表示状态按星期估算"
    )
    degraded: bool = Field(default=False, description="true 表示上游失败、展示的是旧缓存")
    degraded_reason: str | None = Field(default=None, description="降级原因，便于排查")
    source: str = Field(default="东方财富（AkShare）")
    refresh_seconds: int = Field(default=15, description="轮询兜底时的建议间隔")
    push_seconds: int = Field(default=5, description="SSE 推送间隔（也是心跳间隔）")


class TrendPoint(BaseModel):
    trade_date: date
    close: float


class IndexTrendItem(BaseModel):
    code: str
    name: str
    points: list[TrendPoint] = Field(default_factory=list)
    change_pct: float | None = Field(default=None, description="区间涨跌幅（%）")


class IndexTrendsData(BaseModel):
    days: int
    items: list[IndexTrendItem] = Field(default_factory=list)
    as_of: datetime


class IndexMinutePoint(BaseModel):
    """一个分钟点。time 只给 HH:MM，日期由 trade_date 统一说明。"""

    time: str = Field(description="分钟时间，如 09:31")
    price: float = Field(description="该分钟收盘点位")
    avg_price: float | None = Field(default=None, description="当日累计均价")
    volume: float | None = Field(default=None, description="该分钟成交量（手）")
    amount: float | None = Field(default=None, description="该分钟成交额（元）")


class IndexIntradayData(BaseModel):
    """指数当日分时。

    prev_close 单独给出来：分时图的基准线、以及每个点的涨跌幅都靠它算，
    让前端自己从行情快照里找昨收容易在数据缺失时算错。
    """

    code: str
    name: str
    prev_close: float | None = None
    points: list[IndexMinutePoint] = Field(default_factory=list)
    trade_date: date | None = Field(default=None, description="分时所属交易日")
    market_status: str
    status_label: str
    as_of: datetime
    fetched_at: datetime | None = None
    data_as_of: datetime | None = Field(default=None, description="最后一个分时点的时间")
    cache_age_seconds: float | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    calendar_known: bool = True
    source: str = Field(default="东方财富（分时直连）")
    refresh_seconds: int = Field(default=20, description="建议前端刷新间隔")


class IndexCandlePoint(BaseModel):
    """一根日 K。"""

    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = Field(default=None, description="成交量（手）")
    amount: float | None = Field(default=None, description="成交额（元）")


class IndexCandlesData(BaseModel):
    """指数日 K 序列（升序，最后一条是最近交易日）。"""

    code: str
    name: str
    days: int = Field(description="返回的交易日数量（不足则全部返回）")
    points: list[IndexCandlePoint] = Field(default_factory=list)
    as_of: datetime
    fetched_at: datetime | None = None
    data_as_of: datetime | None = Field(default=None, description="最后一根日 K 的收盘时间")
    cache_age_seconds: float | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    calendar_known: bool = True
    source: str = Field(default="东方财富（AkShare）")
