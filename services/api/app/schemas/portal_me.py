"""会员自助（个人中心 / 工作台）的请求/响应模型。

与后台用户 schema 刻意分开：会员只能改展示类字段，
不能碰 is_active、username、密码（密码走独立的改密端点）。
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class PositionCreateRequest(BaseModel):
    """新增模拟持仓：只录金额，份额 = 金额 / 买入净值。"""

    code: str = Field(min_length=6, max_length=12, description="基金代码")
    amount: float = Field(gt=0, le=100_000_000, description="买入金额（元）")
    cost_nav: float = Field(gt=0, le=1000, description="买入时单位净值")
    bought_at: date | None = Field(default=None, description="模拟买入日期，缺省为今天")
    note: str | None = Field(default=None, max_length=200, description="备注")


class PositionUpdateRequest(BaseModel):
    """编辑持仓：字段全部可选，未提供的保持原值。"""

    amount: float | None = Field(default=None, gt=0, le=100_000_000)
    cost_nav: float | None = Field(default=None, gt=0, le=1000)
    bought_at: date | None = Field(default=None)
    note: str | None = Field(default=None, max_length=200)


class PositionItem(BaseModel):
    """持仓明细：份额/市值/盈亏全部由服务端按最新净值计算。"""

    id: int
    code: str
    name: str
    type: str
    sector: str | None = None
    amount: float = Field(description="买入金额（成本，元）")
    cost_nav: float
    bought_at: date
    note: str | None = None
    shares: float = Field(description="份额 = 金额 / 买入净值")
    latest_nav: float | None = None
    latest_nav_date: date | None = None
    market_value: float | None = Field(default=None, description="当前市值（元）")
    profit: float | None = Field(default=None, description="浮动盈亏（元）")
    profit_rate: float | None = Field(default=None, description="浮动收益率（%）")
    created_at: datetime | None = None


class PositionSummary(BaseModel):
    count: int = 0
    total_amount: float = Field(default=0, description="总投入成本（元）")
    total_market_value: float | None = Field(default=None, description="总市值（元）")
    total_profit: float | None = Field(default=None, description="总浮动盈亏（元）")
    profit_rate: float | None = Field(default=None, description="总浮动收益率（%）")
    valued_count: int = Field(default=0, description="已取得最新净值的持仓笔数")


class ProfileUpdateRequest(BaseModel):
    """资料更新：字段全部可选，未提供的保持原值；传空字符串表示清空。"""

    email: EmailStr | None = Field(default=None, description="邮箱，传 null/空表示清空")
    full_name: str | None = Field(default=None, max_length=50, description="显示名称")
    avatar_url: str | None = Field(default=None, max_length=255, description="头像地址")


class PasswordConfirm(BaseModel):
    """敏感操作（注销账号）的二次密码校验。"""

    password: str = Field(min_length=1, description="当前登录密码")


class DashboardSummary(BaseModel):
    total_funds: int = Field(default=0, description="关注基金数")
    avg_return: float | None = Field(default=None, description="所选区间平均收益率（%）")
    positive_ratio: float | None = Field(default=None, description="正收益占比（%）")
    avg_sharpe: float | None = Field(default=None, description="平均夏普比率")
    best_return: float | None = Field(default=None, description="最高区间收益（%）")
    added_last_7_days: int = Field(default=0, description="近 7 天新增关注")
    metric_coverage: float = Field(default=0, description="已补齐区间指标的占比（%）")
    latest_nav_date: str | None = Field(default=None, description="关注基金的最新净值日期")


class DashboardDistributionItem(BaseModel):
    key: str
    label: str
    count: int
    avg_return: float | None = None


class DashboardFundItem(BaseModel):
    code: str
    name: str
    type: str
    sector: str | None = None
    risk_level: str | None = None
    return_rate: float | None = None
    max_drawdown: float | None = None
    sharpe: float | None = None
    latest_nav: float | None = None
    favored_at: datetime | None = None


class DashboardResponse(BaseModel):
    """工作台一次性返回的聚合数据，避免页面发十几个请求。"""

    period: str
    summary: DashboardSummary
    type_distribution: list[DashboardDistributionItem] = Field(default_factory=list)
    risk_distribution: list[DashboardDistributionItem] = Field(default_factory=list)
    sector_distribution: list[DashboardDistributionItem] = Field(default_factory=list)
    return_buckets: list[DashboardDistributionItem] = Field(default_factory=list)
    top_funds: list[DashboardFundItem] = Field(default_factory=list)
    recent_funds: list[DashboardFundItem] = Field(default_factory=list)
    favorites: list[DashboardFundItem] = Field(
        default_factory=list, description="完整收藏列表（按关注时间倒序）"
    )
    positions: list[PositionItem] = Field(default_factory=list, description="模拟持仓明细")
    position_summary: PositionSummary = Field(default_factory=PositionSummary)
