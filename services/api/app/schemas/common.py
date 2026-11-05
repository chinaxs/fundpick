"""通用响应 / 分页模型。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应包装。"""

    code: int = Field(default=0, description="业务码，0 表示成功")
    message: str = Field(default="ok", description="提示信息")
    data: T | None = Field(default=None, description="业务数据")
    request_id: str | None = Field(default=None, description="请求追踪 ID")

    @classmethod
    def ok(cls, data: T | None = None, message: str = "ok") -> "ApiResponse[T]":
        return cls(code=0, message=message, data=data)


class PageResult(BaseModel, Generic[T]):
    """分页结果。"""

    items: list[T] = Field(default_factory=list, description="当前页数据")
    total: int = Field(default=0, description="总条数")
    page: int = Field(default=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, description="每页条数")

    @property
    def pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size else 0


class PageParams(BaseModel):
    """通用分页查询参数。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class IdResponse(BaseModel):
    id: int


class MessageResponse(BaseModel):
    message: str
