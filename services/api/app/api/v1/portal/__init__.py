"""门户接口：面向匿名访客，只读、可公开缓存。

约定：
- 全部挂在 `/api/v1/portal/**`，**不引入** `CurrentUser` / `SuperUser` 依赖；
- 只返回已发布/公开数据，写操作一律不在这里；
- 允许 CDN / 反向代理缓存（无用户态差异）。

会员体系在 `auth.py`：路径 `/api/v1/portal/auth/**`，与后台的 `/admin/auth/**` 隔离。
门户注册的账号 `is_staff=False`，配合 `/admin/**` 的 `StaffUser` 依赖，
两边身份互不通用。
"""

from fastapi import APIRouter

from app.api.v1.portal import articles, auth, funds, stats

router = APIRouter(prefix="/portal")
router.include_router(auth.router)
router.include_router(funds.router)
router.include_router(stats.router)
router.include_router(articles.router)

__all__ = ["router"]
