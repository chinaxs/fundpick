"""公开交易费率缓存及查询来源。"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FundFeeSchedule(Base):
    __tablename__ = "fund_fee_schedules"
    fund_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("funds.id"), primary_key=True)
    rules: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    source_url: Mapped[str] = mapped_column(String(300), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
