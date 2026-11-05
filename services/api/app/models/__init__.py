"""ORM 模型统一出口。

Alembic 的 target_metadata 依赖此处的导入，新增模型务必在此注册。
"""

from app.db.base import Base
from app.models.article import Article, ArticleStatus
from app.models.fund import Fund, FundStatus, FundType, RiskLevel
from app.models.fund_company import FundCompany, FundManager
from app.models.fund_favorite import FundFavorite
from app.models.fund_metric import FundMetric, MetricPeriod
from app.models.fund_nav import FundNav
from app.models.fund_sector import FundSector
from app.models.user import User

__all__ = [
    "Article",
    "ArticleStatus",
    "Base",
    "Fund",
    "FundCompany",
    "FundFavorite",
    "FundManager",
    "FundMetric",
    "FundNav",
    "FundSector",
    "FundStatus",
    "FundType",
    "MetricPeriod",
    "RiskLevel",
    "User",
]
