"""Persistent refresh attempts for on-demand fund NAV/holdings data."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FundDataCheck(Base):
    __tablename__ = "fund_data_checks"

    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)
