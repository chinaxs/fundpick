"""基金板块归属（第二期启用）。

行业板块需要从季报持仓推算，采集成本高、更新频率低（季度），
因此第一期只建表不填充，等持仓数据接入后再写入。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FundSector(TimestampMixin, Base):
    __tablename__ = "fund_sectors"
    __table_args__ = (
        UniqueConstraint("fund_id", "sector_code", name="uq_sector_fund_code"),
        Index("ix_sector_code", "sector_code"),
        {"comment": "基金板块归属表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True
    )
    sector_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="板块编码")
    sector_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="板块名称")
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="该板块持仓占比（%）"
    )
    source: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="来源：holding（持仓推算）/ manual（人工）"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundSector fund={self.fund_id} {self.sector_code}>"
