"""后台接口：需登录，含写操作与敏感数据。

约定：
- 全部挂在 `/api/v1/admin/**`，与门户的 `/portal/**` 严格分离；
- 鉴权走 `staff_users` 表（后台员工），门户会员的令牌 scope 不同，进不来；
- 每个端点都必须显式声明鉴权依赖（`StaffUser` / `SuperUser`），
  即使某个接口"看起来不需要"，也不要放进本包；
- 不作为缓存目标（响应含用户态数据）。

`auth.py` 是后台员工的登录入口（staff_users 表），与门户的 `/portal/auth`
（users 表）是两套独立账号，靠令牌 scope 隔离。
"""

from fastapi import APIRouter

from app.api.v1.admin import (
    ai,
    articles,
    audit_logs,
    auth,
    dashboard,
    funds,
    staff,
    support,
    system,
    users,
)

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(audit_logs.router)
router.include_router(users.router)
router.include_router(staff.router)
router.include_router(articles.router)
router.include_router(funds.router)
router.include_router(support.router)
router.include_router(system.router)
router.include_router(ai.router)

__all__ = ["router"]
