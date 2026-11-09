"""AkShare 数据源实现。

数据来源是东方财富等公开页面，**仅适用于开发验证与非商业用途**。
商业化前必须替换为持牌数据源，见 docs/adr/0006-fund-data-source.md。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import akshare as ak
from pandas import DataFrame

from app.core.logging import get_logger
from app.datasources.base import (
    FundBasic,
    FundHolding,
    FundProfile,
    FundSnapshot,
    IndexCandle,
    IndexDailyPoint,
    IndexIntraday,
    IndexQuote,
    NavPoint,
    RiskMetric,
)
from app.datasources.eastmoney import fetch_intraday

# 数据源的中文周期 -> 内部周期
PERIOD_MAP = {"近1年": "1y", "近3年": "3y", "近5年": "5y"}

logger = get_logger(__name__)


def _to_float(value: Any) -> float | None:
    """把 '1.234' / '0.15%' / '---' / NaN 统一转成 float 或 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if value != value else float(value)  # NaN 判断
    text = str(value).strip().replace("%", "").replace(",", "")
    if text in _EMPTY_TOKENS:
        return None
    try:
        return float(text)
    except ValueError:
        return None


_EMPTY_TOKENS = {"", "---", "--", "nan", "NaN", "NaT", "None", "null"}


def _to_date(value: Any) -> date | None:
    # 注意：pandas 的 NaT 是 datetime 的子类，必须先按字符串判空，
    # 否则会走到 isinstance 分支并把 NaT 原样传给数据库。
    if value is None or str(value).strip() in _EMPTY_TOKENS:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_quarter(text: str) -> str | None:
    """'2025年2季度股票投资明细' → '2025Q2'；无法解析返回 None。"""
    import re

    match = re.search(r"(\d{4})年\s*[一二三四1-4]\s*季度", text)
    if not match:
        return None
    year = match.group(1)
    q_map = {"一": "1", "二": "2", "三": "3", "四": "4"}
    q = text[match.start() : match.end()]
    digit = next((v for k, v in q_map.items() if k in q), None)
    if digit is None:
        digit = next((c for c in q if c.isdigit()), None)
    return f"{year}Q{digit}" if digit else None


class AkShareProvider:
    """基于 AkShare 的实现。方法都是同步阻塞的，调用方需放进线程池。"""

    name = "akshare"

    def list_funds(self) -> list[FundBasic]:
        df: DataFrame = ak.fund_name_em()
        result: list[FundBasic] = []
        for row in df.itertuples(index=False):
            code = str(getattr(row, "基金代码", "")).strip()
            if not code:
                continue
            result.append(
                FundBasic(
                    code=code,
                    name=str(getattr(row, "基金简称", "")).strip(),
                    raw_type=str(getattr(row, "基金类型", "")).strip(),
                )
            )
        return result

    def list_snapshots(self, category: str) -> list[FundSnapshot]:
        df: DataFrame = ak.fund_open_fund_rank_em(symbol=category)
        snapshots: list[FundSnapshot] = []
        for row in df.itertuples(index=False):
            code = str(getattr(row, "基金代码", "")).strip()
            if not code:
                continue
            snapshots.append(
                FundSnapshot(
                    code=code,
                    name=str(getattr(row, "基金简称", "")).strip(),
                    nav_date=_to_date(getattr(row, "日期", None)),
                    unit_nav=_to_float(getattr(row, "单位净值", None)),
                    accum_nav=_to_float(getattr(row, "累计净值", None)),
                    daily_return=_to_float(getattr(row, "日增长率", None)),
                    return_1w=_to_float(getattr(row, "近1周", None)),
                    return_1m=_to_float(getattr(row, "近1月", None)),
                    return_3m=_to_float(getattr(row, "近3月", None)),
                    return_6m=_to_float(getattr(row, "近6月", None)),
                    return_1y=_to_float(getattr(row, "近1年", None)),
                    return_2y=_to_float(getattr(row, "近2年", None)),
                    return_3y=_to_float(getattr(row, "近3年", None)),
                    return_ytd=_to_float(getattr(row, "今年来", None)),
                    return_all=_to_float(getattr(row, "成立来", None)),
                    fee_rate=_to_float(getattr(row, "手续费", None)),
                )
            )
        return snapshots

    def fund_profile(self, code: str) -> FundProfile | None:
        try:
            df: DataFrame = ak.fund_individual_basic_info_xq(symbol=code)
        except Exception as exc:  # 单只失败不影响整体
            logger.debug("基金档案 %s 获取失败: %s", code, exc)
            return None

        info = {str(row[0]).strip(): str(row[1]).strip() for row in df.itertuples(index=False)}
        # "最新规模" 形如 "29.19亿"，去掉单位转数值
        scale_text = info.get("最新规模", "").replace("亿", "").strip()

        # 真实费率来自雪球的费用明细表（管理费/托管费/销售服务费按年计提）。
        # 注意：排行接口的"手续费"是申购费，不能当管理费用（C 类申购费为 0）。
        fees = self._load_fees(code)
        return FundProfile(
            full_name=info.get("基金全称") or None,
            scale=_to_float(scale_text),
            inception_date=_to_date(info.get("成立时间")),
            company_name=info.get("基金公司") or None,
            management_fee=fees.get("基金管理费"),
            custody_fee=fees.get("基金托管费"),
            sales_service_fee=fees.get("销售服务费"),
        )

    @staticmethod
    def _load_fees(code: str) -> dict[str, float | None]:
        """解析雪球费用表：费用类型='其他费用' 的按年计提费率。"""
        try:
            df: DataFrame = ak.fund_individual_detail_info_xq(symbol=code)
        except Exception as exc:
            logger.debug("基金费率 %s 获取失败: %s", code, exc)
            return {}

        result: dict[str, float | None] = {}
        for row in df.itertuples(index=False):
            if str(getattr(row, "费用类型", "")).strip() != "其他费用":
                continue
            name = str(getattr(row, "条件或名称", "")).strip()
            if name in {"基金管理费", "基金托管费", "销售服务费"}:
                result[name] = _to_float(getattr(row, "费用", None))
        return result

    def fund_holdings(self, code: str, year: str) -> list[FundHolding]:
        """东财接口一次返回该基金当年已披露季度的重仓股。

        接口的"序号"列不可信：有时是季度内排名（1-10），有时是全年累计
        （Q2 从 11 起），甚至不同调用返回的覆盖范围都不一致。
        因此这里完全不依赖序号——按季度分组、占净值比例降序重排。
        """
        df: DataFrame = ak.fund_portfolio_hold_em(symbol=code, date=year)
        by_quarter: dict[str, dict[str, FundHolding]] = {}
        for row in df.itertuples(index=False):
            # "2025年2季度股票投资明细" → "2025Q2"
            quarter = _normalize_quarter(str(getattr(row, "季度", "")))
            if quarter is None:
                continue
            stock_code = str(getattr(row, "股票代码", "")).strip()
            if not stock_code:
                continue
            ratio = _to_float(getattr(row, "占净值比例", None)) or 0.0
            # 同一股票同季度可能出现两份披露（全年累计序号 vs 单季），
            # 保留占比更高（更完整披露）的那份
            bucket = by_quarter.setdefault(quarter, {})
            existing = bucket.get(stock_code)
            if existing is not None and (existing.ratio or 0) >= ratio:
                continue
            bucket[stock_code] = FundHolding(
                quarter=quarter,
                stock_code=stock_code,
                stock_name=str(getattr(row, "股票名称", "")).strip(),
                rank=0,  # 分组后重排
                ratio=_to_float(getattr(row, "占净值比例", None)),
                shares=_to_float(getattr(row, "持股数", None)),
                # 上游单位为万元；API和页面统一为亿元。
                market_value=(
                    round(value / 10000, 4)
                    if (value := _to_float(getattr(row, "持仓市值", None))) is not None
                    else None
                ),
            )

        holdings: list[FundHolding] = []
        for _quarter, stocks in by_quarter.items():
            ranked = sorted(stocks.values(), key=lambda h: h.ratio or 0, reverse=True)
            for rank, item in enumerate(ranked, start=1):
                item.rank = rank
                holdings.append(item)
        return holdings

    def transaction_fees(self, code: str) -> list[dict[str, str]]:
        from app.datasources.fund_fees import fetch_fee_rules

        return fetch_fee_rules(code)

    def risk_metrics(self, code: str) -> list[RiskMetric]:
        df: DataFrame = ak.fund_individual_analysis_xq(symbol=code)
        metrics: list[RiskMetric] = []
        for row in df.itertuples(index=False):
            raw_period = str(getattr(row, "周期", "")).strip()
            period = PERIOD_MAP.get(raw_period)
            if period is None:
                continue
            metrics.append(
                RiskMetric(
                    period=period,
                    volatility=_to_float(getattr(row, "年化波动率", None)),
                    sharpe=_to_float(getattr(row, "年化夏普比率", None)),
                    max_drawdown=_to_float(getattr(row, "最大回撤", None)),
                    source="雪球基金分析",
                )
            )
        return metrics

    def nav_history(self, code: str) -> list[NavPoint]:
        df: DataFrame = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        points: list[NavPoint] = []
        for row in df.itertuples(index=False):
            nav_date = _to_date(getattr(row, "净值日期", None))
            nav = _to_float(getattr(row, "单位净值", None))
            if nav_date is None or nav is None:
                continue
            points.append(
                NavPoint(
                    nav_date=nav_date,
                    unit_nav=nav,
                    daily_return=_to_float(getattr(row, "日增长率", None)),
                )
            )
        points.sort(key=lambda p: p.nav_date)
        return points

    def index_quotes(self) -> list[IndexQuote]:
        """沪深重要指数实时快照。

        东财的这张表把上证/深证/中证/北证的核心指数放在一起（约 40 个），
        单次请求即可；延迟通常在数秒到十几秒，非交易时段返回最近收盘值。
        """
        df: DataFrame = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
        quotes: list[IndexQuote] = []
        for row in df.itertuples(index=False):
            code = str(getattr(row, "代码", "")).strip()
            if not code:
                continue
            quotes.append(
                IndexQuote(
                    code=code,
                    name=str(getattr(row, "名称", "")).strip(),
                    price=_to_float(getattr(row, "最新价", None)),
                    change=_to_float(getattr(row, "涨跌额", None)),
                    change_pct=_to_float(getattr(row, "涨跌幅", None)),
                    open=_to_float(getattr(row, "今开", None)),
                    high=_to_float(getattr(row, "最高", None)),
                    low=_to_float(getattr(row, "最低", None)),
                    prev_close=_to_float(getattr(row, "昨收", None)),
                    amplitude=_to_float(getattr(row, "振幅", None)),
                    volume=_to_float(getattr(row, "成交量", None)),
                    amount=_to_float(getattr(row, "成交额", None)),
                )
            )
        return quotes

    def index_daily(self, symbol: str) -> list[IndexDailyPoint]:
        """指数日线收盘序列，symbol 需带市场前缀（sh/sz/bj）。"""
        df: DataFrame = ak.stock_zh_index_daily_em(symbol=symbol)
        points: list[IndexDailyPoint] = []
        for row in df.itertuples(index=False):
            trade_date = _to_date(getattr(row, "date", None))
            close = _to_float(getattr(row, "close", None))
            if trade_date is None or close is None:
                continue
            points.append(IndexDailyPoint(trade_date=trade_date, close=close))
        points.sort(key=lambda p: p.trade_date)
        return points

    def index_candles(self, symbol: str) -> list[IndexCandle]:
        """指数日 K：开盘、最高、最低、收盘 + 量额。

        东财这张表直接给了 OHLC，不用自己拼；停牌日可能缺字段，
        缺关键价的整根丢掉，避免图上出现断点或 0 值。
        """
        df: DataFrame = ak.stock_zh_index_daily_em(symbol=symbol)
        candles: list[IndexCandle] = []
        for row in df.itertuples(index=False):
            trade_date = _to_date(getattr(row, "date", None))
            open_price = _to_float(getattr(row, "open", None))
            high = _to_float(getattr(row, "high", None))
            low = _to_float(getattr(row, "low", None))
            close = _to_float(getattr(row, "close", None))
            if (
                trade_date is None
                or open_price is None
                or high is None
                or low is None
                or close is None
            ):
                continue
            candles.append(
                IndexCandle(
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=_to_float(getattr(row, "volume", None)),
                    amount=_to_float(getattr(row, "amount", None)),
                )
            )
        candles.sort(key=lambda c: c.trade_date)
        return candles

    def index_intraday(self, symbol: str, ndays: int = 1) -> IndexIntraday | None:
        """指数分时序列。

        走东财 trends2 直连而不是 akshare 的分钟接口：后者按 17 个分页拉取，
        实测 22 秒，详情页等不起。见 app/datasources/eastmoney.py 的说明。
        """
        return fetch_intraday(_secid(symbol), ndays=ndays)


def _secid(symbol: str) -> str:
    """sh000001 -> 1.000001；sz399001 / bj899050 -> 0.xxxxxx。

    东财用 1 表示上交所，0 表示深交所与北交所。
    """
    prefix, code = symbol[:2], symbol[2:]
    return f"{1 if prefix == 'sh' else 0}.{code}"
