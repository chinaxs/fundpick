"""运营效果指标。

返回的是**原始计数**，比例交给前端算：后台页面需要同时展示分母
（例如 7 天内新增 12 人、活跃 5 人），只给百分比反而不好核对。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.engagement import EngagementRepository
from app.schemas.admin import EngagementPoint, EngagementSummary

EXCLUDED_NOTE = (
    "已排除测试帐号：用户名以 test / tmp_ / ts_ / tf_ / tp_ / tu_ / qa_ / demo 开头，"
    "或邮箱域名为 example.com / test.local。"
)
DEFINITIONS = (
    "活跃取会员每日访问记录（登录后访问任一页面即记一次，同一天只计一次）；"
    "回访为 7 天内在至少 2 个不同日期访问过；"
    "次周留存取 7–14 天前注册的会员在最近 7 天回来的比例；"
    "关注转化为有自选的会员占比，记账转化为有有效流水或待确认申请的会员占比。"
)


class EngagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EngagementRepository(session)

    async def summary(self) -> EngagementSummary:
        daily = await self.repo.daily_active(14)
        return EngagementSummary(
            total_users=await self.repo.total_users(),
            new_7d=await self.repo.new_users(7),
            active_7d=await self.repo.active_users(7),
            active_30d=await self.repo.active_users(30),
            returning_7d=await self.repo.returning_users(7, 2),
            retention_cohort=await self.repo.cohort_size(8, 7),
            retention_7d=await self.repo.retention(8, 7),
            users_with_favorite=await self.repo.users_with_favorite(),
            users_with_transaction=await self.repo.users_with_transaction(),
            daily_active=[EngagementPoint(day=day, users=users) for day, users in daily],
            excluded_note=EXCLUDED_NOTE,
            definitions=DEFINITIONS,
        )
