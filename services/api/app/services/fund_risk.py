"""Risk measures from disclosed daily returns, including dividend adjustments.

No inference from raw unit NAV: distributions/splits would create false drawdowns.
Annualized volatility uses sample standard deviation × sqrt(252), Sharpe uses
arithmetic daily mean × sqrt(252) / daily std, risk-free rate explicitly zero.
"""

import math
from datetime import date, timedelta
from itertools import pairwise
from statistics import mean, stdev
from typing import Any

SOURCE = "东方财富日涨跌幅测算（252日/年，无风险利率0）"
PERIOD_DAYS = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "3y": 1095, "5y": 1825, "all": None}


def calculate_risk(
    points: list[Any], period: str, inception: date | None = None
) -> tuple[dict[str, float | None] | None, str | None]:
    if len(points) < 2:
        return None, "历史净值不足，暂无法计算"
    end = points[-1].nav_date
    days = PERIOD_DAYS[period]
    start = end - timedelta(days=days) if days else inception or points[0].nav_date
    if days and inception and inception > start:
        return None, "成立时间不足该区间"
    if points[0].nav_date > start + timedelta(days=7):
        return None, "历史净值未覆盖完整区间"
    # Include first observation after the boundary; prior return belongs outside it.
    window = [point for point in points if point.nav_date > start]
    if not window or (window[0].nav_date - start).days > 14:
        return None, "历史净值未覆盖完整区间"
    if any((right.nav_date - left.nav_date).days > 14 for left, right in pairwise(window)):
        return None, "净值序列存在较长缺口，暂不按日年化"
    if any(
        point.daily_return is None
        or not math.isfinite(float(point.daily_return))
        or float(point.daily_return) <= -100
        for point in window
    ):
        return None, "日涨跌幅不完整，暂不计算风险指标"
    returns = [float(point.daily_return) / 100 for point in window]
    wealth, peak, drawdown = 1.0, 1.0, 0.0
    for change in returns:
        wealth *= 1 + change
        peak = max(peak, wealth)
        drawdown = max(drawdown, 1 - wealth / peak)
    result: dict[str, float | None] = {
        "max_drawdown": round(drawdown * 100, 4),
        "volatility": None,
        "sharpe": None,
    }
    if len(returns) >= 20:
        sigma = stdev(returns)
        result["volatility"] = round(sigma * math.sqrt(252) * 100, 4)
        result["sharpe"] = (
            round(mean(returns) / sigma * math.sqrt(252), 4) if sigma > 1e-12 else None
        )
        if sigma <= 1e-12:
            return result, "日收益无波动，夏普比率无定义"
    return result, None if len(returns) >= 20 else "有效样本不足20个，暂不年化"
