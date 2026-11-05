"""用户相关 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="登录名")
    email: EmailStr | None = Field(default=None, description="邮箱")
    full_name: str | None = Field(default=None, max_length=50, description="姓名 / 昵称")


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72, description="登录密码")
    # 后台创建的用户默认是后台账号；门户注册走 /portal/auth/register，写死 False
    is_staff: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    """全部字段可选，仅更新传入的字段。"""

    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    avatar_url: str | None = None
    is_active: bool | None = None
    is_staff: bool | None = None
    is_superuser: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    avatar_url: str | None = None
    is_active: bool
    is_staff: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserQuery(BaseModel):
    keyword: str | None = Field(default=None, description="按用户名 / 邮箱模糊搜索")
    is_active: bool | None = None
