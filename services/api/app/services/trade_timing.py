"""真实交易时间校验：申请日、净值所属日和平台确认日不可混用。"""

from datetime import datetime
from decimal import Decimal

from app.core.exceptions import ValidationError
from app.models.fund import Fund
from app.repositories.transaction import TransactionRepository
from app.schemas.portfolio import TradeInput, TradeTimingInput, TradeTimingRead
from app.trading_calendar import CALENDAR_SOURCE, CLOSURES, SHANGHAI, local_time, nav_day

REGULAR_TYPES = {"stock", "hybrid", "bond", "index"}


def validate_application_time(value: datetime):
    local = local_time(value)
    if local > datetime.now(SHANGHAI):
        raise ValidationError("申请时间不能晚于当前时间")
    return local


def expected_day(fund: Fund, request: TradeTimingInput):
    local = validate_application_time(request.submitted_at)
    if fund.inception_date and local.date() < fund.inception_date:
        raise ValidationError("申请时间早于基金成立日期")
    if request.pricing_rule == "platform":
        return None
    if request.pricing_rule == "auto" and (
        str(fund.type) not in REGULAR_TYPES or local.year not in CLOSURES
    ):
        return None
    if str(fund.type) not in REGULAR_TYPES:
        raise ValidationError("该品种不适用统一15:00规则，请选择按平台回执日期记录")
    if request.pricing_rule == "auto":
        try:
            return nav_day(local)
        except ValidationError:
            return None  # 跨出已核对年份时保留未知，不猜日期。
    return nav_day(local)


async def timing(repo: TransactionRepository, request: TradeTimingInput) -> TradeTimingRead:
    fund = await repo.find_fund(request.code)
    if fund is None:
        raise ValidationError("基金不存在")
    day = expected_day(fund, request)
    value = await repo.exact_nav(fund, day) if day else None
    return TradeTimingRead(
        pricing_rule="cn_open" if day else "platform",
        submitted_at=local_time(request.submitted_at),
        expected_nav_on=day,
        official_nav=str(value) if value is not None else None,
        calendar_source=CALENDAR_SOURCE if day else None,
        message=(
            "使用该净值所属日的官方净值；未公布时等待平台确认。"
            if day
            else "此记录按平台实际回执确定净值日，不套用境内统一截止规则。"
        ),
    )


def validate_receipt(request: TradeInput, fund: Fund) -> None:
    if request.record_source != "receipt":
        return
    assert request.submitted_at and request.pricing_rule
    if not (request.platform or "").strip():
        raise ValidationError("交易平台不能为空")
    local = validate_application_time(request.submitted_at)
    today = datetime.now(SHANGHAI).date()
    if request.settled_on and (
        request.settled_on > today or request.settled_on < request.confirmed_on
    ):
        raise ValidationError("平台确认日不得早于净值所属日或晚于今天")
    if request.confirmed_on < local.date():
        raise ValidationError("净值所属日不能早于申请日期")
    day = expected_day(
        fund,
        TradeTimingInput(
            code=request.code, submitted_at=request.submitted_at, pricing_rule=request.pricing_rule
        ),
    )
    if day is not None and day != request.confirmed_on:
        raise ValidationError(
            f"按申请时间应使用 {day} 净值；请核对，特殊规则请改为平台回执并填写原因"
        )
    if request.pricing_rule == "platform" and not (request.date_reason or "").strip():
        raise ValidationError("按平台日期记录需填写依据，例如平台回执或产品特殊交易规则")


def receipt_warnings(request: TradeInput, nav: Decimal) -> list[str]:
    """尾差保留并提示，不将平台份额或净收入重算覆盖。"""
    if request.record_source != "receipt":
        return []
    if request.kind == "buy":
        assert request.confirmed_shares is not None and request.amount is not None
        difference = abs(request.confirmed_shares * nav + request.fee - request.amount)
    else:
        assert request.shares is not None and request.received_amount is not None
        difference = abs(request.shares * nav - request.fee - request.received_amount)
    warnings = ["按你录入的平台回执记账；本站尚未与交易平台直接核验。"]
    if difference > Decimal("0.02"):
        warnings.append(
            f"金额与份额×净值存在 {difference:.4f} 元差异，请核对回执，系统将保留原值。"
        )
    return warnings
