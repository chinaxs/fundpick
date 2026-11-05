"""基金公司与基金经理。

单独成表而不是在 funds 里存字符串：公司会被大量基金引用，
规范化后便于按公司筛选、统计公司旗下产品的整体表现。
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.fund import Fund


class FundCompany(TimestampMixin, Base):
    """基金管理人（如易方达、华夏）。"""

    __tablename__ = "fund_companies"
    __table_args__ = {"comment": "基金公司表"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True, comment="公司全称"
    )
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="简称")

    funds: Mapped[list[Fund]] = relationship(back_populates="company")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundCompany {self.name}>"


class FundManager(TimestampMixin, Base):
    """基金经理。

    注意：姓名可能重复，唯一性靠 (name, company_id) 组合，不要只按姓名去重。
    """

    __tablename__ = "fund_managers"
    __table_args__ = (
        UniqueConstraint("name", "company_id", name="uq_manager_name_company"),
        Index("ix_managers_company", "company_id"),
        {"comment": "基金经理表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="姓名")
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fund_companies.id"), nullable=True, comment="所属公司"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="从业起始日")
    tenure_years: Mapped[float | None] = mapped_column(nullable=True, comment="任职年限（年）")
    managed_scale: Mapped[float | None] = mapped_column(nullable=True, comment="管理规模（亿元）")
    best_return: Mapped[float | None] = mapped_column(nullable=True, comment="任期最佳回报（%）")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundManager {self.name}>"
