"""v1 路由汇总。

按**调用方**分三组，URL 前缀即归属，看地址就能判断权限要求：

| 前缀 | 调用方 | 鉴权 |
| --- | --- | --- |
| `/api/v1/portal/**` | 门户网站（浏览器匿名 + SSR） | 无 |
| `/api/v1/admin/**` | 后台管理（运营/管理员） | 必须登录，部分需超管 |
| `/api/v1/health/**` | 负载均衡、监控 | 无 |

新增接口时先判断"谁在调用"，再放进对应子包，不要平铺回本文件。
"""

from fastapi import APIRouter

from app.api.v1 import admin, common, portal

api_router = APIRouter()
api_router.include_router(common.router)
api_router.include_router(portal.router)
api_router.include_router(admin.router)
