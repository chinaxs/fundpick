"""门户会员的请求/响应模型。

与后台的 `schemas.user` 刻意分开：门户只暴露展示需要的字段，
不把 `is_staff` / `is_superuser` / `last_login_at` 这类内部状态泄露给浏览器。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册。用户名限制为字母数字与下划线，避免与 URL、日志格式冲突。"""

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_]+$",
        description="登录名（字母/数字/下划线，3–50 位）",
        examples=["fund_fan"],
    )
    email: EmailStr | None = Field(default=None, description="邮箱，可选")
    password: str = Field(min_length=8, max_length=72, description="密码（至少 8 位）")


class PortalUserRead(BaseModel):
    """当前登录会员的最小信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime

    @property
    def display_name(self) -> str:
        return self.full_name or self.username
