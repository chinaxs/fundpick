"""会员访问打卡。

`CurrentUser` 通过校验后调用一次 `touch()`：按天写一行访问记录。
写库走独立会话（不占用请求事务），并做 10 分钟进程内节流——
一个用户一天最多新增 1 行，但不会每个请求都写。

为什么不放中间件：这里需要"已认证的会员 ID"，中间件拿不到解析后的身份，
硬塞会把鉴权逻辑复制一遍。
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic

from sqlalchemy.dialects.mysql import insert

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.member_activity import MemberActivity
from app.trading_calendar import SHANGHAI

logger = get_logger(__name__)

# 同一会员同一自然日内的写库间隔（秒）
TOUCH_INTERVAL_SECONDS = 600
_MAX_CACHE = 5000
_touched: dict[tuple[int, object], float] = {}


def _throttled(user_id: int, day: object, now: float) -> bool:
    key = (user_id, day)
    last = _touched.get(key)
    if last is not None and now - last < TOUCH_INTERVAL_SECONDS:
        return True
    if len(_touched) > _MAX_CACHE:  # 简单清理，避免长期运行内存膨胀
        for stale in [item for item in _touched if item[1] != day]:
            _touched.pop(stale, None)
    _touched[key] = now
    return False


async def touch(user_id: int) -> None:
    """记录一次访问（同一天内节流）。失败不影响请求本身。"""
    now = datetime.now(SHANGHAI)
    if _throttled(user_id, now.date(), monotonic()):
        return
    try:
        async with async_session_factory() as session:
            stmt = insert(MemberActivity).values(
                user_id=user_id,
                activity_date=now.date(),
                last_seen_at=now.replace(tzinfo=None),
            )
            stmt = stmt.on_duplicate_key_update(last_seen_at=stmt.inserted.last_seen_at)
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:  # 活跃统计不能拖垮业务请求
        logger.warning("记录会员活跃失败 user=%s: %s", user_id, exc)


def reset_throttle() -> None:
    """测试用：清空节流缓存。"""
    _touched.clear()


__all__ = ["TOUCH_INTERVAL_SECONDS", "reset_throttle", "touch"]
