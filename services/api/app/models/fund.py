"""基金主数据。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.fund_company import FundCompany, FundManager


class FundType(StrEnum):
    """基金类型。与销售平台的分类口径保持一致，便于用户理解。"""

    STOCK = "stock"
    HYBRID = "hybrid"
    BOND = "bond"
    INDEX = "index"
    QDII = "qdii"
    MONEY = "money"
    FOF = "fof"
    OTHER = "other"


class RiskLevel(StrEnum):
    """风险等级（销售适当性五级分类）。"""

    LOW = "low"
    MID_LOW = "mid_low"
    MID = "mid"
    MID_HIGH = "mid_high"
    HIGH = "high"


class FundStatus(StrEnum):
    OPEN = "open"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Fund(TimestampMixin, SoftDeleteMixin, Base):
    """公募基金主数据。

    latest_nav / latest_nav_date 是冗余字段：列表页需要展示最新净值，
    每次 JOIN 净值表取最新一条代价太高，改由采集任务在写入净值时同步更新。
    """

    __tablename__ = "funds"
    __table_args__ = (
        Index("ix_funds_type_scale", "type", "scale"),
        {"comment": "基金表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(12), nullable=False, unique=True, index=True, comment="基金代码"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="基金简称")
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="基金全称")
    # 搜索用的派生列：全拼与首字母，由 app.fund_search 生成。
    # 不加索引——LIKE '%xx%' 用不到 B+ 树，索引只会拖慢写入。
    name_pinyin: Mapped[str | None] = mapped_column(
        String(120), nullable=True, comment="名称全拼（小写无分隔），供模糊搜索"
    )
    name_initials: Mapped[str | None] = mapped_column(
        String(60), nullable=True, comment="名称拼音首字母，供模糊搜索"
    )

    type: Mapped[FundType] = mapped_column(
        String(20), nullable=False, index=True, default=FundType.OTHER, comment="基金类型"
    )
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        String(20), nullable=True, index=True, comment="风险等级"
    )
    sector: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        comment="主题板块（按名称/跟踪指数推导，见 app.fund_sectors）",
    )
    status: Mapped[FundStatus] = mapped_column(
        String(20), nullable=False, default=FundStatus.OPEN, comment="运作状态"
    )

    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fund_companies.id"), nullable=True, index=True, comment="基金公司"
    )
    manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fund_managers.id"), nullable=True, index=True, comment="现任经理"
    )

    inception_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="成立日期")
    scale: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True, comment="规模（亿元）"
    )
    management_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="管理费率（%/年）"
    )
    custody_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="托管费率（%/年）"
    )

    is_index: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", comment="是否指数基金"
    )
    tracking_index: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="跟踪标的指数"
    )

    latest_nav: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, comment="最新单位净值（冗余）"
    )
    latest_nav_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True, comment="最新净值日期（冗余）"
    )

    company: Mapped[FundCompany | None] = relationship(back_populates="funds")
    manager: Mapped[FundManager | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Fund {self.code} {self.name}>"
