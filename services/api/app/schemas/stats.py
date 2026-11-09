"""首页与筛选页需要的聚合统计。

为什么单独成接口而不是前端聚合：
- 前端只能拿到当前页的 20 条，算不出全市场分布；
- 聚合在数据库侧做（GROUP BY），一次查询比拉 2 万条到前端更省。
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.models.fund import FundType


class TypeStat(BaseModel):
    type: FundType
    label: str
    count: int
    avg_return: float | None = Field(default=None, description="该类型近1年平均收益（%）")


class OverviewStats(BaseModel):
    total_funds: int = Field(description="有净值数据的基金总数")
    total_companies: int
    latest_nav_date: date | None = None
    type_distribution: list[TypeStat] = Field(default_factory=list)


class DistributionBucket(BaseModel):
    label: str
    count: int
    min: float | None = None
    max: float | None = None


class ReturnDistribution(BaseModel):
    period: str
    total: int
    buckets: list[DistributionBucket] = Field(default_factory=list)
