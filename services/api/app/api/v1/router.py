"""v1 路由汇总。新增模块在这里挂载即可。"""

from fastapi import APIRouter

from app.api.v1.endpoints import articles, auth, health, portal, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(articles.router)
api_router.include_router(portal.router)
