"""运营效果指标查询。

口径说明（后台页面也会展示）：

- **一律排除测试帐号**：用户名以 test/tmp_/ts_/tf_/tp_/tu_/qa_/demo 开头，
  或邮箱域名是 example.com / test.local。前缀里的 `_` 用 autoescape 转义，
  否则 `ts_` 会把 "tsa..." 这类真实账号也误排除。
- **活跃取自 `member_activity`**：鉴权通过后按天写一行访问记录。
  不能再用登录会话的创建时间——持续登录的用户不会每天新建会话。
- **回访**是 7 天内有 ≥2 个不同日期访问过的会员数。
- **次周留存**队列是"7–14 天前注册"，统计窗口是"最近 7 天"，与页面文案一致。
- **记账转化**只算有效流水（已确认、未作废、未删除），并计入"已有待确认申请"
  的会员——他们确实开始了第一次记账，只是还没入账。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund_favorite import FundFavorite
from app.models.fund_transaction import FundTransaction
from app.models.member_activity import MemberActivity
from app.models.trade_application import TradeApplication
from app.models.user import User
from app.trading_calendar import SHANGHAI

TEST_USERNAME_PREFIXES = ("test", "tmp_", "ts_", "tf_", "tp_", "tu_", "qa_", "demo")
TEST_EMAIL_DOMAINS = ("example.com", "test.local", "localhost")


def today() -> date:
    """统计口径固定用北京时间：服务器部署在别的时区也不会错一天。"""
    return datetime.now(SHANGHAI).date()


def window_start(days: int) -> date:
    """含今天在内的 days 个自然日的起点（近 7 天 = 今天与之前 6 天）。"""
    return today() - timedelta(days=max(days, 1) - 1)


def _start_dt(day: date) -> datetime:
    return datetime.combine(day, time.min)


def _exclude_test(stmt: Select[Any]) -> Select[Any]:
    """排除测试帐号；前缀与域名都做 LIKE 转义，避免 `_` 当通配符。

    邮箱部分必须是 **AND**：任何一个邮箱都"不属于"除自己域名外的其它域名，
    用 OR 拼多个"不以 X 结尾"会让条件恒真，测试账号一个都排不掉。
    """
    return stmt.where(
        User.deleted_at.is_(None),
        *[~User.username.startswith(prefix, autoescape=True) for prefix in TEST_USERNAME_PREFIXES],
        or_(
            User.email.is_(None),
            and_(
                *[
                    ~User.email.endswith(f"@{domain}", autoescape=True)
                    for domain in TEST_EMAIL_DOMAINS
                ]
            ),
        ),
    )


class EngagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _scalar(self, stmt: Select[Any]) -> int:
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def total_users(self) -> int:
        return await self._scalar(_exclude_test(select(func.count()).select_from(User)))

    async def new_users(self, days: int) -> int:
        since = _start_dt(window_start(days))
        return await self._scalar(
            _exclude_test(select(func.count()).select_from(User)).where(User.created_at >= since)
        )

    async def active_users(self, days: int) -> int:
        """近 days 个自然日（含今天）有访问记录的会员数。"""
        return await self._scalar(_exclude_test(self._activity_window(days)))

    async def returning_users(self, days: int = 7, min_days: int = 2) -> int:
        """窗口内有 ≥min_days 个不同日期访问过的会员数。"""
        since, until = window_start(days), today()
        inner = (
            select(MemberActivity.user_id)
            .join(User, User.id == MemberActivity.user_id)
            .where(
                MemberActivity.activity_date >= since,
                MemberActivity.activity_date <= until,
            )
            .group_by(MemberActivity.user_id)
            .having(func.count(func.distinct(MemberActivity.activity_date)) >= min_days)
        )
        return await self._scalar(select(func.count()).select_from(_exclude_test(inner).subquery()))

    async def retention(self, cohort_days_ago: int = 7, window_days: int = 7) -> int:
        """注册于 7–14 天前的会员，在最近 7 天（含今天）回来过的数量。"""
        start, end, since = self._cohort_range(cohort_days_ago, window_days)
        stmt = (
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .join(MemberActivity, MemberActivity.user_id == User.id)
            .where(
                User.created_at >= start,
                User.created_at < end,
                MemberActivity.activity_date >= since,
                MemberActivity.activity_date <= today(),
            )
        )
        return await self._scalar(_exclude_test(stmt))

    async def cohort_size(self, cohort_days_ago: int = 7, window_days: int = 7) -> int:
        start, end, _ = self._cohort_range(cohort_days_ago, window_days)
        return await self._scalar(
            _exclude_test(select(func.count()).select_from(User)).where(
                User.created_at >= start, User.created_at < end
            )
        )

    @staticmethod
    def _cohort_range(cohort_days_ago: int, window_days: int) -> tuple[datetime, datetime, date]:
        """队列 = 注册于 [今天-14, 今天-7) 的会员；窗口 = 最近 7 个自然日。"""
        current = today()
        start = _start_dt(current - timedelta(days=cohort_days_ago + window_days))
        end = _start_dt(current - timedelta(days=cohort_days_ago))
        return start, end, window_start(window_days)

    @staticmethod
    def _activity_window(days: int) -> Select[Any]:
        return (
            select(func.count(func.distinct(MemberActivity.user_id)))
            .select_from(MemberActivity)
            .join(User, User.id == MemberActivity.user_id)
            .where(
                MemberActivity.activity_date >= window_start(days),
                MemberActivity.activity_date <= today(),
            )
        )

    async def users_with_favorite(self) -> int:
        stmt = (
            select(func.count(func.distinct(FundFavorite.user_id)))
            .select_from(FundFavorite)
            .join(User, User.id == FundFavorite.user_id)
        )
        return await self._scalar(_exclude_test(stmt))

    async def users_with_transaction(self) -> int:
        """已入账（有效）或已有待确认申请的会员，都算"开始记账"。"""
        recorded = (
            await self.session.execute(
                _exclude_test(
                    select(FundTransaction.user_id)
                    .join(User, User.id == FundTransaction.user_id)
                    .where(
                        FundTransaction.deleted_at.is_(None),
                        FundTransaction.status == "confirmed",
                        FundTransaction.voided_at.is_(None),
                    )
                    .distinct()
                )
            )
        ).scalars()
        pending = (
            await self.session.execute(
                _exclude_test(
                    select(TradeApplication.user_id)
                    .join(User, User.id == TradeApplication.user_id)
                    .where(TradeApplication.status == "pending")
                    .distinct()
                )
            )
        ).scalars()
        return len(set(recorded) | set(pending))

    async def daily_active(self, days: int = 14) -> list[tuple[str, int]]:
        stmt = (
            select(
                MemberActivity.activity_date,
                func.count(func.distinct(MemberActivity.user_id)),
            )
            .select_from(MemberActivity)
            .join(User, User.id == MemberActivity.user_id)
            .where(
                MemberActivity.activity_date >= window_start(days),
                MemberActivity.activity_date <= today(),
            )
            .group_by(MemberActivity.activity_date)
            .order_by(MemberActivity.activity_date)
        )
        rows: list[Any] = list((await self.session.execute(_exclude_test(stmt))).all())
        return [(str(row[0]), int(row[1])) for row in rows]


__all__ = ["TEST_EMAIL_DOMAINS", "TEST_USERNAME_PREFIXES", "EngagementRepository"]
