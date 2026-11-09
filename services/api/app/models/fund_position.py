"""模拟持仓模型。

只记录用户录入的「买入金额 + 买入时净值」，份额由 amount / cost_nav 计算，
不落库冗余字段——改金额或改净值都自动重算，避免出现份额与金额对不上的脏数据。
同一基金允许多笔持仓（分批建仓），因此不加唯一约束。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class FundPosition(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fund_positions"
    __table_args__ = (
        Index("ix_position_user_created", "user_id", "created_at"),
        {"comment": "模拟持仓（会员自建，不涉及真实交易）"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="会员 ID"
    )
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True, comment="基金 ID"
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, comment="买入金额（元）"
    )
    cost_nav: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, comment="买入日期对应的单位净值（系统自动取）"
    )
    cost_nav_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="成本净值对应的交易日"
    )
    nav_source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="history",
        server_default="history",
        comment="净值来源：history=历史净值 / latest=回退最新净值",
    )
    bought_at: Mapped[date] = mapped_column(Date, nullable=False, comment="模拟买入日期")
    note: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="备注")
