"""应用入口：create_app 工厂 + 生命周期 + 全局中间件与异常处理。"""

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.core.openapi import DOC_GROUPS, build_subset_schema
from app.db.session import dispose_engine, engine

logger = get_logger(__name__)


# ---------------------------------------------------------------- 生命周期
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("启动 %s [%s] ...", settings.APP_NAME, settings.APP_ENV)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(
            "数据库连接正常：%s:%s/%s",
            settings.MYSQL_HOST,
            settings.MYSQL_PORT,
            settings.MYSQL_DB,
        )
    except Exception as exc:  # 数据库未就绪不阻塞启动，便于容器编排
        logger.warning("数据库连接失败：%s", exc)
    yield
    await dispose_engine()
    logger.info("应用已关闭")


# ---------------------------------------------------------------- 中间件
class RequestContextMiddleware(BaseHTTPMiddleware):
    """注入 request_id 并记录访问日志。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"
        logger.info(
            "%s %s -> %s (%.1fms) rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response


# ---------------------------------------------------------------- 文档分组
# 顺序即 Swagger 的展示顺序：先门户（对外）、再后台（对内）、最后基础设施。
# 每个 tag 带权限说明，避免联调时误调受限接口。
OPENAPI_TAGS = [
    {
        "name": "门户 · 会员",
        "description": "门户注册与登录。**匿名可访问；注册出的账号不能登入后台。**",
    },
    {
        "name": "门户 · 自选",
        "description": "我的关注：添加/取消/列表。**需要登录（门户会员或后台账号）。**",
    },
    {
        "name": "门户 · 基金",
        "description": "门户基金数据：筛选排行、详情、指标、净值。**匿名可访问，只读。**",
    },
    {"name": "门户 · 统计", "description": "门户首页聚合统计。**匿名可访问，只读。**"},
    {"name": "门户 · 内容", "description": "门户研报/文章。**匿名可访问，只读。**"},
    {
        "name": "后台 · 认证",
        "description": "后台账号登录、刷新令牌、当前用户、改密。",
    },
    {"name": "后台 · 用户", "description": "后台用户管理。**需要超管权限。**"},
    {"name": "后台 · 内容", "description": "后台文章管理（增删改查、发布/撤回）。**需要登录。**"},
    {"name": "后台 · 基金", "description": "后台基金数据管理与同步状态。**需要登录。**"},
    {
        "name": "后台 · AI",
        "description": "AI 助手与内容质检。**需要登录；未配置模型密钥时返回 503。**",
    },
    {"name": "公共 · 健康检查", "description": "探活与数据库连通性。**无鉴权，供监控使用。**"},
]


# ---------------------------------------------------------------- 应用工厂
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description=(
            "project_study 后端服务。\n\n"
            "接口按调用方分为三组，路径前缀即归属：\n\n"
            "- `/api/v1/portal/**` —— 门户网站，匿名只读\n"
            "- `/api/v1/admin/**` —— 后台管理，必须登录（部分需超管）\n"
            "- `/api/v1/health/**` —— 探活，无鉴权\n"
        ),
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # localhost / 127.0.0.1 / [::1] 在浏览器中是三个不同的源，
        # 逐个枚举会漏配；开发环境用正则统一放行本机。
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    _register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    _register_api_docs(app)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {
            "app": settings.APP_NAME,
            "api": settings.API_V1_PREFIX,
            "docs": {
                "portal": "/docs/portal",
                "admin": "/docs/admin",
                "all": "/docs",
            },
        }

    return app


def _register_api_docs(app: FastAPI) -> None:
    """注册按消费方切分的文档页：/docs/portal 与 /docs/admin。

    与全量 /docs 并存——日常各看一份避免误调，排查跨端问题时仍可看全量。
    必须在 include_router 之后调用，否则抓到的 schema 是空的。
    """
    if settings.is_production:
        return

    # 取一次完整 schema，再按前缀切片；切完注册的路由都 include_in_schema=False，
    # 不会反过来污染全量文档。
    full = app.openapi()

    def make_openapi_endpoint(schema: dict[str, Any]) -> Callable[[], Awaitable[JSONResponse]]:
        async def endpoint() -> JSONResponse:
            return JSONResponse(schema)

        return endpoint

    def make_docs_endpoint(key: str, title: str) -> Callable[[], Awaitable[HTMLResponse]]:
        async def endpoint() -> HTMLResponse:
            return get_swagger_ui_html(
                openapi_url=f"/openapi/{key}.json",
                title=title,
            )

        return endpoint

    for group in DOC_GROUPS:
        schema = build_subset_schema(full, group)
        app.add_api_route(
            f"/openapi/{group.key}.json",
            make_openapi_endpoint(schema),
            methods=["GET"],
            include_in_schema=False,
            name=f"openapi_{group.key}",
        )
        app.add_api_route(
            f"/docs/{group.key}",
            make_docs_endpoint(group.key, group.title),
            methods=["GET"],
            include_in_schema=False,
            name=f"docs_{group.key}",
        )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(x) for x in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": 42200,
                "message": "参数校验失败",
                "data": details,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": 50000,
                "message": (
                    "服务器内部错误" if settings.is_production else f"{type(exc).__name__}: {exc}"
                ),
                "data": None,
                "request_id": getattr(request.state, "request_id", None),
            },
        )


app = create_app()
