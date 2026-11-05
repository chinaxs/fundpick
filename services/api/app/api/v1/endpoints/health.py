"""健康检查：给负载均衡 / K8s 探针用。"""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings
from app.schemas.common import ApiResponse

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="存活探针")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.VERSION}


@router.get("/health/db", summary="数据库连通性检查")
async def health_db(session: SessionDep) -> ApiResponse[dict[str, str]]:
    await session.execute(text("SELECT 1"))
    return ApiResponse.ok({"database": "ok", "db": settings.MYSQL_DB})
