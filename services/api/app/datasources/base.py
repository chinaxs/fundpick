"""数据源抽象：业务层只依赖这里的协议，不直接依赖 akshare。

为什么要这一层：
现在用 AkShare（免费、抓公开页），将来商业化必须换成持牌数据源（Wind / Choice / 聚源）。
如果采集脚本直接写 `ak.xxx()`，换源就要改遍全程；有了这层，只需实现一个新类。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(slots=True)
class FundBasic:
    """基金基础信息。"""

    code: str
    name: str
    raw_type: str  # 数据源的原始类型描述，如"混合型-灵活"


@dataclass(slots=True)
class FundSnapshot:
    """某只基金在某个时点的快照：最新净值 + 各区间收益。

    区间收益直接来自数据源，不在本地重算——省一轮全量净值采集。
    """

    code: str
    name: str
    nav_date: date | None = None
    unit_nav: float | None = None
    accum_nav: float | None = None
    daily_return: float | None = None
    return_1w: float | None = None
    return_1m: float | None = None
    return_3m: float | None = None
    return_6m: float | None = None
    return_1y: float | None = None
    return_2y: float | None = None
    return_3y: float | None = None
    return_ytd: float | None = None
    return_all: float | None = None
    fee_rate: float | None = None


@dataclass(slots=True)
class FundProfile:
    """单只基金档案（逐只请求才能拿到的字段）。"""

    full_name: str | None = None
    scale: float | None = None
    inception_date: date | None = None
    company_name: str | None = None
    # 费率（%/年）。注意与管理费区分：申购费是一次性费用，不在这里。
    management_fee: float | None = None
    custody_fee: float | None = None
    # C 类份额用销售服务费替代申购费，同样按年计提
    sales_service_fee: float | None = None


@dataclass(slots=True)
class FundHolding:
    """单只基金某个季度的重仓股。"""

    quarter: str  # 归一化格式，如 "2025Q2"
    stock_code: str
    stock_name: str
    rank: int  # 第几大重仓
    ratio: float | None = None  # 占净值比例（%）
    shares: float | None = None  # 持股数（万股）
    market_value: float | None = None  # 持仓市值（亿元）


@dataclass(slots=True)
class RiskMetric:
    """风险指标（由数据源直接提供，避免本地全量算净值）。"""

    period: str  # 1y / 3y / 5y
    volatility: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    source: str | None = None


@dataclass(slots=True)
class NavPoint:
    """单个净值点。"""

    nav_date: date
    unit_nav: float
    daily_return: float | None = None


@dataclass(slots=True)
class IndexQuote:
    """指数实时快照（一次请求取回全部跟踪指数）。

    字段口径与行情软件一致：涨跌幅单位是 %，成交额单位是元。
    """

    code: str
    name: str
    price: float | None = None
    change: float | None = None  # 涨跌额
    change_pct: float | None = None  # 涨跌幅（%）
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    amplitude: float | None = None  # 振幅（%）
    volume: float | None = None  # 成交量（手）
    amount: float | None = None  # 成交额（元）


@dataclass(slots=True)
class IndexDailyPoint:
    """指数日线收盘点，只用于画迷你走势。"""

    trade_date: date
    close: float


@dataclass(slots=True)
class IndexMinuteBar:
    """指数分时点（1 分钟粒度）。

    一个交易日 241 个点（09:30–11:30、13:00–15:00 含两端）。
    均价是当日累计成交额/成交量，画在分时图上就是那条黄线。
    """

    moment: datetime
    price: float  # 该分钟收盘点位
    avg_price: float | None = None
    volume: float | None = None  # 该分钟成交量（手）
    amount: float | None = None  # 该分钟成交额（元）


@dataclass(slots=True)
class IndexIntraday:
    """指数当日分时序列 + 昨收（画基准线、算涨跌幅都要用）。"""

    name: str
    prev_close: float | None
    points: list[IndexMinuteBar]


@dataclass(slots=True)
class IndexCandle:
    """指数日 K 的一根蜡烛。

    K 线需要开高低收 + 量额，`IndexDailyPoint` 只有收盘价，
    是给迷你走势图用的，两者不要合并——否则列表页要多传 6 个用不上的字段。
    """

    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None  # 成交量（手）
    amount: float | None = None  # 成交额（元）


class FundDataProvider(Protocol):
    """基金数据源协议。新增数据源实现这三个方法即可。"""

    name: str

    def list_funds(self) -> list[FundBasic]:
        """全量基金列表（代码、名称、类型）。"""
        ...

    def list_snapshots(self, category: str) -> list[FundSnapshot]:
        """按类别拉取排行快照。

        Args:
            category: 平台口径的分类，如"股票型""混合型""债券型""指数型""QDII"。
        """
        ...

    def nav_history(self, code: str) -> list[NavPoint]:
        """单只基金的历史净值序列（用于详情页曲线）。"""
        ...

    def fund_profile(self, code: str) -> FundProfile | None:
        """单只基金档案：全称、规模、成立日期、公司、费率。"""
        ...

    def fund_holdings(self, code: str, year: str) -> list[FundHolding]:
        """单只基金某年度各季度的重仓股明细。"""
        ...

    def transaction_fees(self, code: str) -> list[dict[str, str]]:
        """公开申购/赎回费率及原始条件，不含已计入净值的管理托管费。"""
        ...

    def risk_metrics(self, code: str) -> list[RiskMetric]:
        """单只基金的风险指标（波动率、夏普、最大回撤）。"""
        ...

    # ---- 指数行情（市场大盘） ----
    def index_quotes(self) -> list[IndexQuote]:
        """一次取回全部指数的实时快照。

        刻意不做"按代码逐个查"：行情源通常支持一次返回整张表，
        逐个请求既慢又容易被限频。
        """
        ...

    def index_daily(self, symbol: str) -> list[IndexDailyPoint]:
        """单只指数的日线收盘序列（symbol 形如 sh000001）。"""
        ...

    def index_intraday(self, symbol: str, ndays: int = 1) -> IndexIntraday | None:
        """单只指数的分钟级分时序列（symbol 形如 sh000001）。

        一次返回整段分时（当日 241 个点），供详情页画分时图。
        与 index_quotes 的区别是粒度：这里是 1 分钟，那边是"当前快照"。
        """
        ...

    def index_candles(self, symbol: str) -> list[IndexCandle]:
        """单只指数的日 K 全量序列（含开高低收、量额）。

        返回整段历史（上证约 8700 根），由服务层按需截取窗口：
        多取一次和多取一天的成本一样，但缓存命中率更高。
        """
        ...


# 排行接口支持的分类（数据源口径），后续换源时映射到自家枚举
RANK_CATEGORIES: tuple[str, ...] = ("股票型", "混合型", "债券型", "指数型", "QDII", "FOF")
