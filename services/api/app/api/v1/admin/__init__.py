"""后台接口：需登录，含写操作与敏感数据。

约定：
- 全部挂在 `/api/v1/admin/**`，与门户的 `/portal/**` 严格分离；
- 每个端点都必须显式声明鉴权依赖（`CurrentUser` / `SuperUser`），
  即使某个接口"看起来不需要"，也不要放进本包；
- 不作为缓存目标（响应含用户态数据）。

`auth.py` 是后台账号的登录入口。门户将来自己的登录在 `portal/auth.py`，
两边共享 `users` 表时也要用不同的角色校验，不能共用同一个登录接口。
"""

from fastapi import APIRouter

from app.api.v1.admin import ai, articles, audit_logs, auth, dashboard, funds, users

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(audit_logs.router)
router.include_router(users.router)
router.include_router(articles.router)
router.include_router(funds.router)
router.include_router(ai.router)

__all__ = ["router"]
