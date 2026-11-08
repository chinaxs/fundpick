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
    sector: str | None = Field(default=None, description="主题板块，如 new_energy / semiconductor")
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
    sector: str | None = Field(default=None, description="主题板块 key（NULL=综合/无明确主题）")
    company_name: str | None = None
    manager_name: str | None = None

    share_class: str | None = Field(default=None, description="份额类别，如 A/C；非份额基金为 None")
    base_name: str | None = Field(default=None, description="去掉份额类别后的基础名称")

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
    risk_nav_date: date | None = None
    risk_source: str | None = None
    risk_coverage: int = 0
    risk_stale: bool = True
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


class HoldingRead(BaseModel):
    """单只重仓股。"""

    quarter: str
    stock_code: str
    stock_name: str | None = None
    rank: int | None = None
    ratio: float | None = None  # 占净值比例（%）
    shares: float | None = None  # 持股数（万股）
    market_value: float | None = None  # 持仓市值（亿元）


class HoldingsResult(BaseModel):
    """持仓查询结果：可选季度列表 + 当前季度明细。"""

    quarters: list[str] = Field(default_factory=list, description="已披露的季度，倒序")
    quarter: str | None = Field(default=None, description="当前返回的季度")
    items: list[HoldingRead] = Field(default_factory=list)
    total_ratio: float | None = Field(default=None, description="前十大合计占净值比例（%）")


class FilterOption(BaseModel):
    value: str | int
    label: str


class SectorOption(FilterOption):
    """板块筛选项：附带基金数量，便于前端展示热度。"""

    count: int = 0


class FilterOptions(BaseModel):
    """筛选项字典，前端下拉框直接用，避免硬编码枚举。"""

    types: list[FilterOption] = Field(default_factory=list)
    risk_levels: list[FilterOption] = Field(default_factory=list)
    sectors: list[SectorOption] = Field(default_factory=list)
    companies: list[FilterOption] = Field(default_factory=list)
    periods: list[FilterOption] = Field(default_factory=list)
    sort_fields: list[FilterOption] = Field(default_factory=list)


# ---------------------------------------------------------------- 基金对比
COMPARE_PERIODS: tuple[tuple[str, str], ...] = (
    ("3m", "近3月"),
    ("6m", "近6月"),
    ("1y", "近1年"),
    ("3y", "近3年"),
)


class ComparePeriod(BaseModel):
    """某区间的对比项。available=False 表示该区间缺风险数据，不是 0。"""

    period: str
    label: str
    return_rate: float | None = None
    max_drawdown: float | None = None
    sharpe: float | None = None
    volatility: float | None = None
    risk_nav_date: date | None = None
    available: bool = False


class FundCompareItem(BaseModel):
    code: str
    name: str
    share_class: str | None = None
    base_name: str | None = None
    type: FundType
    type_label: str
    risk_level: RiskLevel | None = None
    risk_label: str | None = None
    company_name: str | None = None
    manager_name: str | None = None
    latest_nav: float | None = None
    latest_nav_date: date | None = None
    scale: float | None = None
    fee_rate: float | None = Field(default=None, description="管理费率（%/年）")
    custody_fee: float | None = None
    inception_date: date | None = None
    periods: list[ComparePeriod] = Field(default_factory=list)


class FundCompareResult(BaseModel):
    items: list[FundCompareItem] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=lambda: [period for period, _ in COMPARE_PERIODS])
    note: str = (
        "同一基金的 A/C 等份额收益接近但费率不同，对比前请确认份额类别；"
        "标注「无数据」的区间表示上游未提供风险指标，不代表 0。"
    )
