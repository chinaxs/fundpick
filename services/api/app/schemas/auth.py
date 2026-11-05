"""认证相关模型。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(description="登录名或邮箱")
    password: str = Field(min_length=1, description="密码")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="access_token 有效期（秒）")


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)
