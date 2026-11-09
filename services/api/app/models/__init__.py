"""ORM 模型统一出口。

Alembic 的 target_metadata 依赖此处的导入，新增模型务必在此注册。
"""

from app.db.base import Base
from app.models.article import Article, ArticleStatus
from app.models.article_version import ArticleVersion
from app.models.audit_log import AuditLog
from app.models.auth_session import AuthLoginAttempt, AuthSession
from app.models.fund import Fund, FundStatus, FundType, RiskLevel
from app.models.fund_company import FundCompany, FundManager
from app.models.fund_favorite import FundFavorite
from app.models.fund_fee_schedule import FundFeeSchedule
from app.models.fund_holding import FundHolding
from app.models.fund_metric import FundMetric, MetricPeriod
from app.models.fund_nav import FundNav
from app.models.fund_position import FundPosition
from app.models.fund_sector import FundSector
from app.models.fund_transaction import FundTransaction
from app.models.member_activity import MemberActivity
from app.models.portfolio_flow import FlowKind, FundPortfolioFlow
from app.models.staff import StaffAdminMutex, StaffUser
from app.models.support import Feedback, FeedbackCategory, FeedbackStatus, PasswordResetRequest
from app.models.sync_job import SyncJob, SyncJobMutex, SyncSchedule
from app.models.trade_application import TradeApplication
from app.models.user import User

__all__ = [
    "Article",
    "ArticleStatus",
    "ArticleVersion",
    "AuditLog",
    "AuthLoginAttempt",
    "AuthSession",
    "Base",
    "Feedback",
    "FeedbackCategory",
    "FeedbackStatus",
    "FlowKind",
    "Fund",
    "FundCompany",
    "FundFavorite",
    "FundFeeSchedule",
    "FundHolding",
    "FundManager",
    "FundMetric",
    "FundNav",
    "FundPortfolioFlow",
    "FundPosition",
    "FundSector",
    "FundStatus",
    "FundTransaction",
    "FundType",
    "MemberActivity",
    "MetricPeriod",
    "PasswordResetRequest",
    "RiskLevel",
    "StaffAdminMutex",
    "StaffUser",
    "SyncJob",
    "SyncJobMutex",
    "SyncSchedule",
    "TradeApplication",
    "User",
]
