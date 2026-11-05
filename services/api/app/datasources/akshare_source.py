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
from app.datasources.base import FundBasic, FundSnapshot, NavPoint, RiskMetric

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
