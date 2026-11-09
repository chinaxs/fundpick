"""用户在其他平台提交的待确认申请；不生成持仓或收益。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class TradeApplication(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "trade_applications"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_application_request"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    fund_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("funds.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expected_nav_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    pricing_rule: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    request_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    automatic_processing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    processing_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
