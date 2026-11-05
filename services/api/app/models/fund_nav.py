"""基金净值序列。

这是全库最大的表：1 万只基金 × 每日一条 ≈ 每年 250 万行量级（单只按存续 10 年算可达千万级）。
因此：
- 只存必要字段，不给每行加冗余注释字段；
- 唯一索引 (fund_id, nav_date) 同时服务于"按基金查区间"；
- 批量写入用 upsert，避免先查后插。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FundNav(Base):
    __tablename__ = "fund_navs"
    __table_args__ = (
        UniqueConstraint("fund_id", "nav_date", name="uq_nav_fund_date"),
        Index("ix_nav_date", "nav_date"),
        {"comment": "基金净值表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True
    )
    nav_date: Mapped[date] = mapped_column(Date, nullable=False, comment="净值日期")
    unit_nav: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, comment="单位净值")
    accum_nav: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, comment="累计净值"
    )
    daily_return: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True, comment="日涨跌幅（%）"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundNav fund={self.fund_id} {self.nav_date} {self.unit_nav}>"
