"""模拟交易：输入、预览、确认回执及组合汇总契约。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.portal_me import PortfolioSummary, PositionItem


class TradeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^\d{6}$")
    kind: Literal["buy", "sell"]
    confirmed_on: date = Field(description="净值所属日，兼容字段名；不是平台确认日")
    record_source: Literal["calculated", "receipt", "estimated"] = "calculated"
    submitted_at: datetime | None = None
    settled_on: date | None = None
    platform: str | None = Field(default=None, min_length=1, max_length=80)
    calculation_basis: dict | None = None
    receipt_ref: str | None = Field(default=None, max_length=100)
    pricing_rule: Literal["cn_open", "platform"] | None = None
    date_reason: str | None = Field(default=None, max_length=200)
    confirmed_shares: Decimal | None = Field(default=None, gt=0, le=1_000_000_000, decimal_places=4)
    received_amount: Decimal | None = Field(default=None, ge=0, le=100_000_000, decimal_places=2)
    application_id: int | None = Field(default=None, gt=0)
    nav_mode: Literal["official", "manual"] = "official"
    nav: Decimal | None = Field(default=None, gt=0, le=1_000_000, decimal_places=6)
    amount: Decimal | None = Field(default=None, gt=0, le=100_000_000, decimal_places=2)
    shares: Decimal | None = Field(default=None, gt=0, le=1_000_000_000, decimal_places=4)
    fee: Decimal = Field(default=Decimal(0), ge=0, le=100_000_000, decimal_places=2)
    note: str | None = Field(default=None, max_length=200)
    legacy_position_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_direction(self) -> "TradeInput":
        """买入按含费金额、卖出按份额，禁止含糊或多余的成交字段。"""
        if self.kind == "buy" and (self.amount is None or self.shares is not None):
            raise ValueError("买入请填写含手续费的总金额，不填写卖出份额")
        if self.kind == "sell" and (self.shares is None or self.amount is not None):
            raise ValueError("卖出请填写份额，不填写买入金额")
        if self.nav_mode == "manual" and self.nav is None:
            raise ValueError("请填写确认净值")
        if self.nav_mode == "official" and self.nav is not None:
            raise ValueError("自动净值模式无需手填净值")
        if self.legacy_position_id and self.kind != "buy":
            raise ValueError("旧持仓只能核对为买入记录")
        if self.record_source == "receipt":
            if not self.submitted_at or not self.platform or not self.pricing_rule:
                raise ValueError("请填写购买平台和下单时间")
            if "fee" not in self.model_fields_set:
                raise ValueError("请按平台回执填写实际手续费，无费用填0")
            if self.kind == "buy" and self.confirmed_shares is None:
                raise ValueError("买入必须填写平台实际确认份额")
            if self.kind == "sell" and self.received_amount is None:
                raise ValueError("卖出必须填写平台实际净到账金额")
        elif self.record_source == "calculated" and any(
            value is not None
            for value in (
                self.submitted_at,
                self.settled_on,
                self.platform,
                self.confirmed_shares,
                self.received_amount,
                self.application_id,
            )
        ):
            raise ValueError("交易回执信息必须使用回执记账模式")
        return self


class TradeEffect(BaseModel):
    code: str
    name: str
    kind: Literal["buy", "sell"]
    confirmed_on: date
    nav: float
    nav_source: str
    amount: float
    fee: float
    shares: float
    cash_amount: float
    realized_profit: float
    remaining_shares: float
    remaining_cost: float
    note: str | None = None


class TradePreview(TradeEffect):
    preview_hash: str
    warnings: list[str] = Field(default_factory=list)


class TradeConfirm(BaseModel):
    request: TradeInput
    preview_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_key: UUID


class TradeRead(TradeEffect):
    id: int
    status: str
    can_void: bool = False
    legacy_position_id: int | None = None
    created_at: datetime | None = None
    voided_at: datetime | None = None
    void_reason: str | None = None
    calculation_basis: dict | None = None
    submitted_at: datetime | None = None
    settled_on: date | None = None
    platform: str | None = None
    receipt_ref: str | None = None
    record_source: str = "calculated"
    pricing_rule: str | None = None
    date_reason: str | None = None
    application_id: int | None = None


class TradeVoid(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class HoldingRead(BaseModel):
    estimated_count: int = 0
    code: str
    name: str
    shares: float
    remaining_cost: float
    average_cost: float | None
    latest_nav: float | None
    latest_nav_date: date | None
    market_value: float | None
    holding_profit: float | None
    realized_profit: float
    dividends: float = 0
    total_profit: float | None
    total_buy_amount: float
    total_sell_amount: float
    fees: float
    last_confirmed_on: date


class PortfolioRead(BaseModel):
    holdings: list[HoldingRead]
    summary: PortfolioSummary
    legacy_positions: list[PositionItem] = Field(default_factory=list)


class TradeTimingInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    submitted_at: datetime
    pricing_rule: Literal["auto", "cn_open", "platform"] = "cn_open"


class TradeTimingRead(BaseModel):
    pricing_rule: Literal["cn_open", "platform"]
    submitted_at: datetime
    expected_nav_on: date | None
    official_nav: str | None
    calendar_source: str | None
    message: str


class ApplicationInput(TradeTimingInput):
    kind: Literal["buy", "sell"]
    platform: str | None = Field(default=None, max_length=80)
    amount: Decimal | None = Field(default=None, gt=0, le=100_000_000, decimal_places=2)
    shares: Decimal | None = Field(default=None, gt=0, le=1_000_000_000, decimal_places=4)
    note: str | None = Field(default=None, max_length=200)
    request_key: UUID

    @model_validator(mode="after")
    def direction(self):
        if self.kind == "buy" and (self.amount is None or self.shares is not None):
            raise ValueError("买入填写申请金额")
        if self.kind == "sell" and (self.shares is None or self.amount is not None):
            raise ValueError("卖出填写申请份额")
        return self


class ApplicationRead(BaseModel):
    automatic_processing: bool = False
    requires_review: bool = False
    processing_message: str | None = None
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    id: int
    code: str
    name: str
    kind: str
    platform: str
    submitted_at: datetime
    expected_nav_on: date | None
    pricing_rule: str
    amount: str | None
    shares: str | None
    status: str
    note: str | None


class AutoTradeInput(ApplicationInput):
    pass


class AutoTradeRead(BaseModel):
    status: Literal["recorded", "pending"]
    transaction: TradeRead | None = None
    application: ApplicationRead | None = None
    message: str


class TradeHistoryQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = Field(default=None, max_length=100)
    kind: Literal["buy", "sell"] | None = None
    status: Literal["pending", "confirmed", "cancelled", "voided"] | None = None
    start: date | None = None
    end: date | None = Field(default=None, le=date(9999, 12, 30))

    @model_validator(mode="after")
    def date_range(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError("开始日期不能晚于结束日期")
        return self


class TradeHistoryItem(BaseModel):
    record_type: Literal["transaction", "application"]
    id: int
    code: str
    name: str
    kind: Literal["buy", "sell"]
    status: Literal["pending", "confirmed", "cancelled", "voided"]
    submitted_at: datetime | None = None
    created_at: datetime | None = None
    confirmed_on: date | None = None
    expected_nav_on: date | None = None
    settled_on: date | None = None
    remaining_shares: float | None = None
    remaining_cost: float | None = None
    voided_at: datetime | None = None
    legacy_position_id: int | None = None
    platform: str | None = None
    amount: float | None = None
    shares: float | None = None
    nav: float | None = None
    nav_source: str | None = None
    fee: float | None = None
    cash_amount: float | None = None
    realized_profit: float | None = None
    record_source: str | None = None
    receipt_ref: str | None = None
    calculation_basis: dict | None = None
    void_reason: str | None = None
    note: str | None = None
    can_void: bool = False
    can_cancel: bool = False
    can_delete: bool = False
    requires_review: bool = False
    processing_message: str | None = None
