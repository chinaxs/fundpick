"""后台写操作的审计中间件。

为什么放在中间件而不是在 service 里埋点：

1. 不侵入业务代码，新增接口自动被覆盖，漏埋点的风险为 0；
2. 统一拿到状态码、耗时与来源 IP；
3. 一处修改，全局生效。

局限：**拿不到请求体**——在中间件里读 body 会消费下游的流。
所以记录的是"谁、在什么时间、对哪个资源、做了什么操作、结果如何"，
不做字段级 diff。需要字段级时在 service 里单独补。

`POST /admin/auth/login` 是匿名端点，登录成功前无身份可读；
登录端点在验证通过后会回填 `request.state.username`，因此成功的登录
也能记录操作人，失败尝试仍只保留 IP，用于暴力破解排查。
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.audit_log import AuditLog

logger = get_logger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
AUDIT_PREFIX = "/api/v1/admin"

_ACTION_BY_METHOD = {
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def classify(path: str, method: str) -> tuple[str, str, str | None]:
    """从路径推断 (动作, 资源, 资源 ID)。

    `/api/v1/admin/users/12` → ("update", "users", "12")
    `/api/v1/admin/auth/login` → ("login", "auth", None)
    """
    parts = [part for part in path.split("/") if part]
    # ["api", "v1", "admin", ...]
    resource = parts[3] if len(parts) > 3 else "unknown"
    resource_id = parts[4] if len(parts) > 4 else None

    if resource == "auth":
        tail = parts[4] if len(parts) > 4 else "other"
        return tail, resource, resource_id

    return _ACTION_BY_METHOD.get(method, "other"), resource, resource_id


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def _persist(
    request: Request, response: Response, action: str, resource: str, resource_id: str | None
) -> None:
    user_id = getattr(request.state, "user_id", None)
    username = getattr(request.state, "username", None)
    started = getattr(request.state, "started_at", None)

    duration = None
    if isinstance(started, float):
        duration = int((time.perf_counter() - started) * 1000)

    # 只记参数名，不记值：避免把密码、令牌落进日志表
    query_keys = ",".join(request.query_params.keys()) or None

    # 用独立会话：请求会话可能因异常回滚，审计记录不能跟着丢
    async with async_session_factory() as session:
        session.add(
            AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource=resource,
                resource_id=resource_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                ip=client_ip(request),
                duration_ms=duration,
                detail=query_keys,
            )
        )
        await session.commit()


class AuditMiddleware(BaseHTTPMiddleware):
    """记录 `/api/v1/admin/**` 下的写操作。"""

    async def dispatch(self, request: Request, call_next):
        request.state.started_at = time.perf_counter()
        response = await call_next(request)

        if request.method in WRITE_METHODS and request.url.path.startswith(AUDIT_PREFIX):
            action, resource, resource_id = classify(request.url.path, request.method)
            try:
                await _persist(request, response, action, resource, resource_id)
            except Exception as exc:  # 审计失败不能影响业务响应
                logger.warning("审计日志写入失败：%s", exc)

        return response
