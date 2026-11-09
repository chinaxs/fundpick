"""已确认的模拟交易流水；持仓由有效流水按移动平均成本汇总。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class FundTransaction(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fund_transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="uq_transaction_request"),
        Index("ix_transaction_user_fund_date", "user_id", "fund_id", "confirmed_on", "id"),
        {"comment": "模拟买卖流水，作废保留审计记录"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    fund_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("funds.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    confirmed_on: Mapped[date] = mapped_column(Date, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settled_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    calculation_basis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    receipt_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    record_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="calculated", server_default="calculated"
    )
    pricing_rule: Mapped[str | None] = mapped_column(String(16), nullable=True)
    date_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    application_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trade_applications.id"), nullable=True, unique=True
    )
    nav: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    nav_source: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    realized_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remaining_shares: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    remaining_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    request_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fund_positions.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
