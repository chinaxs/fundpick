"""基金季度重仓股明细。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FundHolding(Base):
    """某基金某季度前十大重仓股。

    quarter 用 "2025Q2" 归一化格式；同一基金同一季度同一股票唯一，
    重复采集按 (fund_id, quarter, stock_code) 幂等覆盖。
    """

    __tablename__ = "fund_holdings"
    __table_args__ = (
        UniqueConstraint("fund_id", "quarter", "stock_code", name="uq_fund_quarter_stock"),
        {"comment": "基金季度重仓股"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True, comment="基金"
    )
    quarter: Mapped[str] = mapped_column(String(8), nullable=False, comment="季度，如 2025Q2")
    stock_code: Mapped[str] = mapped_column(String(12), nullable=False, comment="股票代码")
    stock_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="股票名称")
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="重仓排名（1-10）")

    ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="占净值比例（%）"
    )
    shares: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 4), nullable=True, comment="持股数（万股）"
    )
    market_value: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 4), nullable=True, comment="持仓市值（亿元）"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundHolding {self.fund_id} {self.quarter} {self.stock_code}>"
