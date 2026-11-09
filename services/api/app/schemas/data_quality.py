"""基金数据质量检查结果。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class DataQualitySummary(BaseModel):
    total_funds: int = 0
    affected_funds: int = 0
    missing_nav: int = 0
    lagging_nav: int = 0
    missing_return: int = 0
    stale_risk: int = 0
    missing_profile: int = 0


class DataQualityIssue(BaseModel):
    code: str
    name: str
    fields: list[str] = Field(default_factory=list)
    latest_nav_date: date | None = None
    nav_age_days: int | None = None
    risk_nav_date: date | None = None
    suggested_mode: Literal["snapshot", "risk", "detail"]


class DataQualityReport(BaseModel):
    checked_on: date
    nav_stale_after_days: int
    summary: DataQualitySummary
    items: list[DataQualityIssue] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 100
