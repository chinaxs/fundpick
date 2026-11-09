"""后台员工账号的请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="登录名")
    password: str = Field(min_length=8, max_length=72, description="登录密码")
    email: EmailStr | None = Field(default=None, description="邮箱")
    full_name: str | None = Field(default=None, max_length=50, description="姓名")
    is_superuser: bool = Field(default=False, description="是否超级管理员")


class StaffUpdate(BaseModel):
    """全部字段可选，仅更新传入的字段。"""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    avatar_url: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None


class StaffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StaffQuery(BaseModel):
    keyword: str | None = Field(default=None, description="按用户名 / 邮箱模糊搜索")
    is_active: bool | None = None
