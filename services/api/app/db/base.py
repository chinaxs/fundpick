"""ORM 基类与通用字段 Mixin。"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型继承此基类，Alembic 依赖它收集元数据。"""


class TimestampMixin:
    """创建 / 更新时间，由数据库侧默认值维护。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class SoftDeleteMixin:
    """软删除标记：非空即视为已删除，查询时需过滤。"""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, comment="删除时间（软删除）"
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
