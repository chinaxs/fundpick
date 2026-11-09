"""本站跟踪的核心指数清单与交易时段判定。

为什么固定清单而不是让前端传代码：
- 行情源一次返回几十个指数，服务端过滤只需一次请求，也避免被当成通用行情代理；
- 指数的"代码"在不同数据源含义不同（中证/国证/北证混在一起），
  日线接口还需要 sh/sz/bj 前缀，映射关系集中在这里最不容易出错。

新增指数时只要在这里加一行，接口、前端都会自动带上。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from app.trading_calendar import SHANGHAI, latest_trading_day, trading_day_or_none

# 与交易日历共用同一个时区对象，避免两处"北京时间"出现细微差异
MARKET_TZ = SHANGHAI


@dataclass(frozen=True, slots=True)
class TrackedIndex:
    code: str  # 行情表里的代码
    name: str
    symbol: str  # 日线接口符号（带市场前缀）
    group: str  # 展示分组

    @property
    def short_name(self) -> str:
        return self.name.replace("指数", "")

    @property
    def secid(self) -> str:
        """东财分时接口用的市场号：1 沪市，0 深市/北交所。"""
        return f"{1 if self.symbol.startswith('sh') else 0}.{self.code}"


# 顺序即展示顺序：先看沪深两市，再看成长板块，最后是宽基与北交所。
TRACKED_INDICES: tuple[TrackedIndex, ...] = (
    TrackedIndex("000001", "上证指数", "sh000001", "沪市"),
    TrackedIndex("399001", "深证成指", "sz399001", "深市"),
    TrackedIndex("399006", "创业板指", "sz399006", "成长"),
    TrackedIndex("000688", "科创50", "sh000688", "成长"),
    TrackedIndex("000300", "沪深300", "sh000300", "宽基"),
    TrackedIndex("000905", "中证500", "sh000905", "宽基"),
    TrackedIndex("000852", "中证1000", "sh000852", "宽基"),
    TrackedIndex("899050", "北证50", "bj899050", "北交所"),
)

INDEX_BY_CODE: dict[str, TrackedIndex] = {item.code: item for item in TRACKED_INDICES}

# 交易时段（不含节假日）。节假日无法从行情源直接得知，
# 因此状态只作为"是否轮询"的提示，真实数据时间以 trade_date 为准。
MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)


def calendar_known(today: date | None = None) -> bool:
    """交易日历是否覆盖这一天所在年份。

    未覆盖时不猜测，只把状态降级为"按星期估算"，并通过接口把
    `calendar_known=false` 告诉前端，避免把推断当官方休市安排。
    """
    day = today or datetime.now(MARKET_TZ).date()
    return trading_day_or_none(day) is not None


def calendar_trade_date(today: date | None = None) -> date | None:
    """本地日历推算的最近交易日，用于上游没给 trade_date 时兜底。"""
    return latest_trading_day(today or datetime.now(MARKET_TZ).date())


STATUS_LABELS: dict[str, str] = {
    "pre_open": "未开盘",
    "trading": "交易中",
    "lunch_break": "午间休市",
    "closed": "已收盘",
}


def market_status(now: datetime | None = None) -> str:
    """返回 pre_open / trading / lunch_break / closed。

    交易日判定统一走 `app.trading_calendar`：周末与法定节假日都是 closed。
    日历未覆盖的年份（如 2027）不猜测，退回按星期的粗略判断，
    避免首页因为"日历没维护"直接报错。
    """
    current = (now or datetime.now(MARKET_TZ)).astimezone(MARKET_TZ)
    if current.weekday() >= 5:  # 周六、周日
        return "closed"
    known = trading_day_or_none(current.date())
    if known is False:  # 法定节假日（含调休补班的周末已在上面的分支）
        return "closed"

    moment = current.time()
    if moment < MORNING_OPEN:
        return "pre_open"
    if MORNING_OPEN <= moment < MORNING_CLOSE:
        return "trading"
    if MORNING_CLOSE <= moment < AFTERNOON_OPEN:
        return "lunch_break"
    if AFTERNOON_OPEN <= moment < AFTERNOON_CLOSE:
        return "trading"
    return "closed"
