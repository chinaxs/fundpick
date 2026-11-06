"""门户会员的 Pydantic 模型（users 表）。

后台员工走 `schemas/staff.py`（staff_users 表），两边字段刻意不共享。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="登录名")
    email: EmailStr | None = Field(default=None, description="邮箱")
    full_name: str | None = Field(default=None, max_length=50, description="姓名 / 昵称")


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72, description="登录密码")


class UserUpdate(BaseModel):
    """全部字段可选，仅更新传入的字段。"""

    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    avatar_url: str | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    avatar_url: str | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserQuery(BaseModel):
    keyword: str | None = Field(default=None, description="按用户名 / 邮箱模糊搜索")
    is_active: bool | None = None
