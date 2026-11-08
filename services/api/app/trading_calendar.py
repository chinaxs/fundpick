"""境内证券交易日历：仅使用已核对年度，未知范围拒绝推算。"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import ValidationError

SHANGHAI = ZoneInfo("Asia/Shanghai")
CALENDAR_SOURCE = "https://www.sse.com.cn/disclosure/dealinstruc/closed/"
# 2026 年上交所年度休市安排（2026-11-08 核对），补班周末仍休市。
CLOSURES = {
    2025: (
        ("01-01", "01-01"),
        ("01-28", "02-04"),
        ("04-04", "04-06"),
        ("05-01", "05-05"),
        ("05-31", "06-02"),
        ("10-01", "10-08"),
    ),
    2026: (
        ("01-01", "01-03"),
        ("02-15", "02-23"),
        ("04-04", "04-06"),
        ("05-01", "05-05"),
        ("06-19", "06-21"),
        ("09-25", "09-27"),
        ("10-01", "10-07"),
    ),
}


def local_time(value: datetime) -> datetime:
    """必须提供带时区的申请时间，规范为北京时间，精确到秒。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("申请时间必须包含时区；页面按北京时间录入")
    return value.astimezone(SHANGHAI).replace(microsecond=0)


def is_trading_day(day: date) -> bool:
    if day.year not in CLOSURES:
        raise ValidationError(f"{day.year} 年交易日历尚未核对，请按平台回执记录净值日")
    return day.weekday() < 5 and not any(
        date.fromisoformat(f"{day.year}-{start}") <= day <= date.fromisoformat(f"{day.year}-{end}")
        for start, end in CLOSURES[day.year]
    )


def trading_day_or_none(day: date) -> bool | None:
    """查询是否交易日；年度未核对时返回 None。

    行情状态判定要"猜得保守"而不是抛错：日历没覆盖到的年份里，
    宁可退回按星期的粗略判断，也不能让首页大盘整块 500。
    """
    try:
        return is_trading_day(day)
    except ValidationError:
        return None


def latest_trading_day(day: date, lookback: int = 10) -> date | None:
    """不晚于 day 的最近一个交易日；超出日历范围返回 None。"""
    for offset in range(lookback + 1):
        candidate = day - timedelta(days=offset)
        known = trading_day_or_none(candidate)
        if known is None:
            return None
        if known:
            return candidate
    return None


def nav_day(submitted_at: datetime) -> date:
    """普通境内场外基金：交易日15:00前归当日，否则下一交易日。"""
    current = local_time(submitted_at)
    day = current.date()
    if is_trading_day(day) and current.time() < time(15, 0):
        return day
    day += timedelta(days=1)
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def advance_trading_days(day: date, days: int) -> date:
    """按已核对证券日历推进公开T+N确认周期，不使用普通日历天。"""
    for _ in range(days):
        day += timedelta(days=1)
        while not is_trading_day(day):
            day += timedelta(days=1)
    return day
