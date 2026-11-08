"""统一响应体与业务异常定义。

约定：所有接口返回 HTTP 200/4xx/5xx + 统一 JSON 结构：{code, message, data, request_id}
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="业务码，0 表示成功")
    message: str = Field(default="ok", description="提示信息")
    data: T | None = Field(default=None, description="业务数据")
    request_id: str | None = Field(default=None, description="请求追踪 ID")


class PageResult(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------- 业务异常
class AppException(Exception):
    """所有可预期业务异常的基类。"""

    status_code: int = 400
    code: int = 40000
    message: str = "请求处理失败"

    def __init__(self, message: str | None = None, code: int | None = None, data: Any = None):
        self.message = message or self.message
        self.code = code or self.code
        self.data = data
        super().__init__(self.message)


class UnauthorizedError(AppException):
    status_code = 401
    code = 40100
    message = "未认证或登录已失效"


class ForbiddenError(AppException):
    status_code = 403
    code = 40300
    message = "没有权限执行该操作"


class NotFoundError(AppException):
    status_code = 404
    code = 40400
    message = "资源不存在"


class ConflictError(AppException):
    status_code = 409
    code = 40900
    message = "资源冲突"


class RateLimitError(AppException):
    status_code = 429
    code = 42900
    message = "请求过于频繁，请稍后重试"


class ValidationError(AppException):
    status_code = 422
    code = 42200
    message = "参数校验失败"
