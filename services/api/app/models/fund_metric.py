"""区间指标快照。

为什么单独存表而不是每次实时算：
- 列表页要按"近一年收益"排序 1 万只基金，实时算会拖垮数据库；
- 指标按日计算一次、增量更新，查询就退化成一次带索引的排序；
- 历史指标可留痕，便于做"指标变化"类功能。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MetricPeriod:
    """区间常量。新增区间时在此登记，指标计算任务会按此遍历。"""

    W1 = "1w"
    M1 = "1m"
    M3 = "3m"
    M6 = "6m"
    Y1 = "1y"
    Y2 = "2y"
    Y3 = "3y"
    Y5 = "5y"
    YTD = "ytd"
    ALL = "all"

    # 与数据源口径对齐：排行接口直接提供这些区间的收益率
    ALL_PERIODS = (W1, M1, M3, M6, Y1, Y2, Y3, Y5, YTD, ALL)
    # 列表页默认排序用的区间
    DEFAULT = Y1


class FundMetric(TimestampMixin, Base):
    __tablename__ = "fund_metrics"
    __table_args__ = (
        UniqueConstraint("fund_id", "period", name="uq_metric_fund_period"),
        # 列表页核心查询：某区间按收益倒序
        Index("ix_metric_period_return", "period", "return_rate"),
        Index("ix_metric_period_sharpe", "period", "sharpe"),
        {"comment": "基金区间指标表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="区间：1m/3m/6m/1y/3y/5y/all"
    )
    nav_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="指标计算基准日（最新净值日）"
    )

    return_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, comment="区间收益率（%）"
    )
    annual_return: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, comment="年化收益率（%）"
    )
    max_drawdown: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, comment="最大回撤（%，正数表示回撤幅度）"
    )
    volatility: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, comment="年化波动率（%）"
    )
    sharpe: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True, comment="夏普比率"
    )
    calmar: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True, comment="卡玛比率"
    )

    rank: Mapped[int | None] = mapped_column(nullable=True, comment="同类排名")
    total: Mapped[int | None] = mapped_column(nullable=True, comment="同类总数")
    percentile: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True, comment="排名百分位（越小越靠前）"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundMetric fund={self.fund_id} {self.period} {self.return_rate}>"
