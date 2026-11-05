"""基金相关 Pydantic 模型。"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.fund import FundStatus, FundType, RiskLevel


class FundSortBy(StrEnum):
    """列表可排序字段白名单。不允许前端直接传字段名，避免 SQL 注入。"""

    RETURN = "return"
    SHARPE = "sharpe"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    SCALE = "scale"
    NAV = "nav"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class FundQuery(BaseModel):
    """筛选条件。为空则不加该条件。"""

    keyword: str | None = Field(default=None, description="基金代码或名称模糊搜索")
    type: FundType | None = Field(default=None, description="基金类型")
    risk_level: RiskLevel | None = Field(default=None, description="风险等级")
    company_id: int | None = Field(default=None, description="基金公司")
    period: str = Field(default="1y", description="区间：1w/1m/3m/6m/1y/2y/3y/ytd/all")
    sort_by: FundSortBy = FundSortBy.RETURN
    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class FundListItem(BaseModel):
    """列表项：只带列表页需要的字段，避免把正文类大字段带出来。"""

    id: int
    code: str
    name: str
    type: FundType
    risk_level: RiskLevel | None = None
    company_name: str | None = None
    manager_name: str | None = None

    latest_nav: float | None = None
    latest_nav_date: date | None = None
    scale: float | None = Field(default=None, description="规模（亿元）")
    fee_rate: float | None = Field(default=None, description="管理费率（%/年）")

    return_rate: float | None = Field(default=None, description="所选区间收益率（%）")
    max_drawdown: float | None = Field(default=None, description="最大回撤（%）")
    volatility: float | None = Field(default=None, description="年化波动率（%）")
    sharpe: float | None = Field(default=None, description="夏普比率")
    rank: int | None = None
    total: int | None = None


class FundDetail(FundListItem):
    model_config = ConfigDict(from_attributes=True)

    full_name: str | None = None
    status: FundStatus
    inception_date: date | None = None
    custody_fee: float | None = None
    is_index: bool = False
    tracking_index: str | None = None
    manager_tenure_years: float | None = None
    manager_scale: float | None = None
    manager_best_return: float | None = None


class MetricRead(BaseModel):
    period: str
    return_rate: float | None = None
    annual_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    rank: int | None = None
    total: int | None = None


class NavRange(StrEnum):
    """净值曲线的时间区间。

    与 `MetricPeriod` 分开：这里只关心"画多久的曲线"，
    不涉及排行统计口径（后者含近1周、今年来等）。
    """

    M1 = "1m"
    M3 = "3m"
    M6 = "6m"
    Y1 = "1y"
    Y3 = "3y"
    ALL = "all"

    @property
    def days(self) -> int | None:
        """回溯天数；None 表示不限制（成立以来）。"""
        return {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "3y": 1095}.get(self.value)


class NavPointRead(BaseModel):
    nav_date: date
    unit_nav: float
    daily_return: float | None = None


class FilterOption(BaseModel):
    value: str | int
    label: str


class FilterOptions(BaseModel):
    """筛选项字典，前端下拉框直接用，避免硬编码枚举。"""

    types: list[FilterOption] = Field(default_factory=list)
    risk_levels: list[FilterOption] = Field(default_factory=list)
    companies: list[FilterOption] = Field(default_factory=list)
    periods: list[FilterOption] = Field(default_factory=list)
    sort_fields: list[FilterOption] = Field(default_factory=list)
