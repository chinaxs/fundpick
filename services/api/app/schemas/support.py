"""会员支持：反馈工单、密码重置、会员排查的请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.support import FeedbackCategory, FeedbackStatus

__all__ = [
    "FeedbackCategory",
    "FeedbackCreate",
    "FeedbackRead",
    "FeedbackStatus",
    "FeedbackUpdate",
    "ForgotPasswordRequest",
    "MemberPortfolioItem",
    "MemberPortfolioRead",
    "MemberPositionItem",
    "MemberSupportRead",
    "PasswordResetRead",
    "ResetLinkRead",
    "ResetPasswordRequest",
]

_CATEGORY_VALUES = {item.value for item in FeedbackCategory}


class FeedbackCreate(BaseModel):
    category: str = Field(default="other", description="account / data / function / bug / other")
    title: str = Field(min_length=3, max_length=120)
    content: str = Field(min_length=10, max_length=2000, description="问题描述")
    contact: str | None = Field(default=None, max_length=120, description="联系方式，可选")
    page_url: str | None = Field(default=None, max_length=255, description="出问题的页面")

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str) -> str:
        if value not in _CATEGORY_VALUES:
            raise ValueError("不支持的反馈分类")
        return value


class FeedbackUpdate(BaseModel):
    status: FeedbackStatus | None = None
    reply: str | None = Field(default=None, max_length=2000)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: str
    title: str
    content: str
    contact: str | None = None
    page_url: str | None = None
    status: str
    reply: str | None = None
    handled_by: str | None = None
    handled_at: datetime | None = None
    created_at: datetime


class FeedbackListItem(FeedbackRead):
    """后台列表额外带会员标识，避免逐条再查。"""

    username: str | None = None
    email: str | None = None


class MemberSupportRead(BaseModel):
    """会员支持概览：只给处理问题所需的最小信息。"""

    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    favorite_count: int = 0
    transaction_count: int = 0
    position_count: int = 0
    open_feedback: int = 0
    pending_reset: int = 0


class MemberPortfolioItem(BaseModel):
    """交易明细只读视图：保留来源与状态，便于和用户核对。"""

    id: int
    fund_code: str
    fund_name: str
    kind: str
    status: str
    confirmed_on: date
    submitted_at: datetime | None = None
    shares: float
    amount: float
    fee: float
    nav: float
    record_source: str
    platform: str | None = None
    voided_at: datetime | None = None


class MemberPositionItem(BaseModel):
    fund_code: str
    fund_name: str
    shares: float
    cost: float
    market_value: float | None = None
    updated_at: datetime | None = None


class MemberPortfolioRead(BaseModel):
    user_id: int
    items: list[MemberPortfolioItem] = Field(default_factory=list)
    positions: list[MemberPositionItem] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False
    note: str = "只读排查视图，不提供修改入口；如需更正请让会员本人重新确认或作废后重录。"


class ResetLinkRead(BaseModel):
    user_id: int
    username: str
    token: str = Field(description="一次性令牌，交给会员本人使用")
    expires_at: datetime
    path: str = Field(description="门户重置页路径，含 token")


class PasswordResetRead(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    email: str | None = None
    requested_ip: str | None = None
    created_at: datetime
    used_at: datetime | None = None
    expires_at: datetime | None = None
    issued_by: str | None = None
    pending: bool = False


class ForgotPasswordRequest(BaseModel):
    account: str = Field(min_length=3, max_length=120, description="注册邮箱或登录名")


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)
