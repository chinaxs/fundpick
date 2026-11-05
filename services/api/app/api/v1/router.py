"""v1 路由汇总。新增模块在这里挂载即可。"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_funds,
    ai,
    articles,
    auth,
    health,
    portal,
    portal_funds,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)

# 基金域
api_router.include_router(portal_funds.router)
api_router.include_router(admin_funds.router)

# 内容域（原文章模块，后续改造为研报/基金点评）
api_router.include_router(articles.router)
api_router.include_router(portal.router)

api_router.include_router(ai.router)
