"""ORM 模型统一出口。

Alembic 的 target_metadata 依赖此处的导入，新增模型务必在此注册。
"""

from app.db.base import Base
from app.models.article import Article, ArticleStatus
from app.models.user import User

__all__ = ["Article", "ArticleStatus", "Base", "User"]
