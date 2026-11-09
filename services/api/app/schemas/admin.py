"""后台运营视图的响应模型。"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class AuditQuery(BaseModel):
    """审计日志筛选条件。"""

    username: str | None = Field(default=None, description="按用户名模糊匹配")
    resource: str | None = Field(default=None, description="users/articles/funds/auth")
    action: str | None = Field(default=None, description="create/update/delete/login")
    status_code: int | None = Field(default=None, description="响应状态码")
    start: datetime | None = Field(default=None, description="起始时间")
    end: datetime | None = Field(default=None, description="结束时间")


class AuditLogRead(BaseModel):
    id: int
    username: str | None = None
    action: str
    resource: str
    resource_id: str | None = None
    method: str
    path: str
    status_code: int
    ip: str | None = None
    duration_ms: int | None = None
    detail: str | None = None
    created_at: datetime


class CoverageItem(BaseModel):
    """某一类数据的覆盖情况，用于健康度进度条。"""

    key: str
    label: str
    covered: int
    total: int
    percent: float = Field(description="覆盖率 0–100")


class TypeCount(BaseModel):
    type: str
    label: str
    count: int
    avg_return: float | None = None


class RecentUser(BaseModel):
    """门户会员侧的最近注册（后台员工在独立的 staff_users 表，不混入）。"""

    id: int
    username: str
    email: str | None = None
    created_at: datetime


class DashboardOverview(BaseModel):
    funds_total: int
    companies_total: int
    managers_total: int
    nav_latest_date: date | None = None
    nav_date_lag_days: int | None = Field(
        default=None, description="最新净值日距今的天数，用于判断数据是否及时"
    )
    coverage: list[CoverageItem] = Field(default_factory=list)
    user_total: int = 0
    user_staff: int = 0
    user_new_7d: int = 0
    article_total: int = 0
    article_published: int = 0
    favorite_total: int = 0
    type_distribution: list[TypeCount] = Field(default_factory=list)
    recent_users: list[RecentUser] = Field(default_factory=list)
    recent_audits: list[AuditLogRead] = Field(default_factory=list)
    server_time: datetime


class TableStat(BaseModel):
    name: str
    rows: int
    comment: str | None = None


class SystemInfo(BaseModel):
    app_name: str
    version: str
    environment: str
    debug: bool
    python_version: str
    database: str = Field(description="脱敏后的连接信息")
    started_at: datetime
    uptime_seconds: int
    tables: list[TableStat] = Field(default_factory=list)


class EngagementPoint(BaseModel):
    """按日活跃趋势的一个点。"""

    day: str
    users: int


class EngagementSummary(BaseModel):
    """运营效果指标（已排除测试帐号）。"""

    total_users: int
    new_7d: int
    active_7d: int
    active_30d: int
    returning_7d: int
    retention_cohort: int = Field(description="7–14 天前注册的会员数")
    retention_7d: int = Field(description="其中最近 7 天回来过的数量")
    users_with_favorite: int
    users_with_transaction: int
    daily_active: list[EngagementPoint] = Field(default_factory=list)
    excluded_note: str = Field(description="测试帐号过滤口径说明")
    definitions: str = Field(description="指标定义说明")
