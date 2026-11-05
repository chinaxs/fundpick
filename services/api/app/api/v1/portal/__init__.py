"""门户接口：面向匿名访客，只读、可公开缓存。

约定：
- 全部挂在 `/api/v1/portal/**`，**不引入** `CurrentUser` / `SuperUser` 依赖；
- 只返回已发布/公开数据，写操作一律不在这里；
- 允许 CDN / 反向代理缓存（无用户态差异）。

将来门户自身的用户体系（自选、组合跟踪）在本包内新增 `auth.py`，
路径为 `/api/v1/portal/auth/**`，与后台的 `/admin/auth/**` 完全隔离——
两套身份互不影响，避免"后台账号能登进门户"这类越权问题。
"""

from fastapi import APIRouter

from app.api.v1.portal import articles, funds, stats

router = APIRouter(prefix="/portal")
router.include_router(funds.router)
router.include_router(stats.router)
router.include_router(articles.router)

__all__ = ["router"]
