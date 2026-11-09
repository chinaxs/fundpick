"""公共接口：不针对特定消费方，供探活与运维使用。

放在 `/api/v1/health/**`，无鉴权、无业务逻辑，可被负载均衡与监控直接探测。
"""

from fastapi import APIRouter

from app.api.v1.common import health

router = APIRouter()
router.include_router(health.router)

__all__ = ["router"]
