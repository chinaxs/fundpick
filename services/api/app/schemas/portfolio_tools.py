"""持仓工具：历史导入、公司行为流水、导出与收益核对。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FLOW_KIND_LABELS: dict[str, str] = {
    "dividend": "现金分红",
    "reinvest": "红利再投",
    "split": "拆分 / 合并",
    "convert_out": "转换转出",
    "convert_in": "转换转入",
}


class ImportRow(BaseModel):
    """一行历史持仓：份额、金额、净值三者填两个即可推出第三个。"""

    code: str = Field(pattern=r"^\d{6}$", description="基金代码")
    confirmed_on: date = Field(description="确认日期（按平台回执）")
    shares: Decimal | None = Field(
        default=None, gt=0, le=1_000_000_000, decimal_places=4, description="确认份额"
    )
    amount: Decimal | None = Field(
        default=None, gt=0, le=100_000_000, decimal_places=2, description="买入金额（含费）"
    )
    nav: Decimal | None = Field(
        default=None, gt=0, le=1_000_000, decimal_places=6, description="确认净值"
    )
    platform: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _enough_numbers(self) -> ImportRow:
        provided = sum(value is not None for value in (self.shares, self.amount, self.nav))
        if provided < 2:
            raise ValueError("份额、金额、净值至少填写两项")
        return self

    @field_validator("confirmed_on")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value > datetime.now().date():
            raise ValueError("确认日期不能晚于今天")
        return value


class ImportRequest(BaseModel):
    rows: list[ImportRow] = Field(min_length=1, max_length=50)
    dry_run: bool = Field(default=False, description="只校验并返回将导入的内容")


class ImportRowError(BaseModel):
    index: int = Field(description="在提交列表中的序号，从 1 开始")
    code: str | None = None
    reason: str


class ImportResult(BaseModel):
    created: int = 0
    dry_run: bool = False
    errors: list[ImportRowError] = Field(default_factory=list)
    imported: list[dict[str, str]] = Field(default_factory=list)


class FlowCreate(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    kind: Literal["dividend", "reinvest", "split", "convert_out", "convert_in"]
    effective_on: date
    cash_amount: Decimal | None = Field(default=None, ge=0, le=100_000_000, decimal_places=2)
    shares_delta: Decimal | None = Field(
        default=None, ge=-1_000_000_000, le=1_000_000_000, decimal_places=4
    )
    nav: Decimal | None = Field(default=None, gt=0, le=1_000_000, decimal_places=6)
    ratio: Decimal | None = Field(default=None, gt=0, le=9999, decimal_places=6)
    target_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    # 转换两侧的实际成交数据：转入份额由对手基金的净值决定，不能复制转出份额
    target_shares: Decimal | None = Field(
        default=None, gt=0, le=1_000_000_000, decimal_places=4, description="转入确认份额"
    )
    target_nav: Decimal | None = Field(
        default=None, gt=0, le=1_000_000, decimal_places=6, description="转入确认净值"
    )
    target_cash_amount: Decimal | None = Field(
        default=None, ge=0, le=100_000_000, decimal_places=2, description="转入金额（含费）"
    )
    platform: str | None = Field(
        default=None,
        max_length=80,
        description="归属平台；多平台持有时必须指定，否则按份额最大的平台归属",
    )
    request_key: str | None = Field(
        default=None, max_length=64, description="幂等键：同一键重复提交只记一笔"
    )
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_required(self) -> FlowCreate:
        if self.kind == "dividend" and not self.cash_amount:
            raise ValueError("现金分红需要填写金额")
        if self.kind == "reinvest":
            if self.shares_delta is None or self.shares_delta <= 0:
                raise ValueError("红利再投需要填写增加的份额")
            if not self.cash_amount and not self.nav:
                # 不能拿原持仓平均成本猜再投金额：那会把红利算成零成本
                raise ValueError("红利再投需要填写再投金额或再投净值，用于确认这笔红利")
        if self.kind == "split" and not self.ratio:
            raise ValueError("拆分/合并需要填写比例")
        if self.kind in {"convert_in", "convert_out"} and not self.target_code:
            raise ValueError("转换需要填写对手基金代码")
        if self.kind == "convert_in" and (self.shares_delta is None or self.shares_delta <= 0):
            raise ValueError("转换转入需要填写转入份额")
        if self.kind == "convert_out" and (self.shares_delta is None or self.shares_delta >= 0):
            raise ValueError("转换转出需要填写减少的份额（负数）")
        if self.target_shares is not None and self.kind not in {"convert_in", "convert_out"}:
            raise ValueError("只有转换可以填写转入份额")
        if self.kind == "dividend" and self.shares_delta is not None:
            raise ValueError("现金分红不改变份额")
        if self.effective_on > datetime.now().date():
            raise ValueError("生效日期不能晚于今天")
        return self


class FlowRead(BaseModel):
    id: int
    code: str
    fund_name: str
    kind: str
    kind_label: str
    effective_on: date
    cash_amount: float | None = None
    net_amount: float | None = Field(
        default=None, description="转换转出的实际结转净额；与 cash_amount 的差是费用"
    )
    shares_delta: float | None = None
    nav: float | None = None
    ratio: float | None = None
    target_code: str | None = None
    platform: str | None = None
    note: str | None = None
    created_at: datetime


class ReconciliationFund(BaseModel):
    code: str
    name: str
    ledger_shares: float
    ledger_cost: float
    flow_shares_delta: float
    flow_cash: float
    expected_shares: float
    note: str | None = None


class ReconciliationResult(BaseModel):
    funds: list[ReconciliationFund] = Field(default_factory=list)
    invested: float = 0
    redeemed: float = 0
    dividends: float = 0
    realized_profit: float = 0
    note: str = (
        "份额以平台回执确认的买卖流水为准；分红、拆分与转换按归属平台并入同一账本，"
        "不自动改写已确认的买卖份额。再投按收到的红利计入收益，不额外算作外部投入。"
    )
    generated_at: datetime
