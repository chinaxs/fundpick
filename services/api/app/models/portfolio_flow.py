"""持仓相关的补充流水：分红、红利再投、拆分、转换。

为什么不塞进 `fund_transactions`：那张表记录的是**平台确认的买卖**，
份额、净值、费用、金额之间有强约束（买入/卖出才能算已实现收益）。
分红与拆分不是买卖，硬塞进去会污染 FIFO 成本与已实现收益的计算。

因此这里单独存"影响持仓但不属于买卖"的事件，并在收益核对里
把两者合并展示，标明哪部分是回执确认、哪部分是公司行为。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FlowKind(StrEnum):
    DIVIDEND = "dividend"  # 现金分红
    REINVEST = "reinvest"  # 红利再投
    SPLIT = "split"  # 份额拆分 / 合并
    CONVERT_OUT = "convert_out"  # 转换转出
    CONVERT_IN = "convert_in"  # 转换转入


class FundPortfolioFlow(TimestampMixin, Base):
    __tablename__ = "fund_portfolio_flows"
    __table_args__ = (
        Index("ix_portfolio_flow_user_fund", "user_id", "fund_id", "effective_on"),
        {"comment": "持仓补充流水：分红/再投/拆分/转换"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="会员"
    )
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True, comment="基金"
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False, comment="事件类型")
    effective_on: Mapped[date] = mapped_column(Date, nullable=False, comment="生效日期")
    cash_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True, comment="现金金额（分红/转换转出的毛金额）"
    )
    net_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="转换转出实际结转净额；毛额与净额之差是转换费用/损耗",
    )
    shares_delta: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 4), nullable=True, comment="份额变动（正数为增加）"
    )
    nav: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 6), nullable=True, comment="事件使用的净值"
    )
    ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True, comment="拆分/合并比例，2 表示 1 份变 2 份"
    )
    target_fund_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=True, comment="转换对手基金"
    )
    transfer_group: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="转换配对标识：同一笔转换的转出与转入共用",
    )
    platform: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
        comment="归属平台；再投/分红/转换只作用于该平台的份额",
    )
    request_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="幂等键：网络重试不会重复记录同一笔公司行为",
    )
    request_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="请求内容摘要：同一个键换了内容必须冲突，不能静默沿用旧记录",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="删除时间；保留墓碑，旧请求重试不会把记录重新入账",
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="备注")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundPortfolioFlow {self.id} {self.kind} user={self.user_id}>"
