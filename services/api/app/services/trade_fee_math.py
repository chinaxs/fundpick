"""交易费率档位与先进先出持有期计算；不接受含糊的条件或费率。"""

import re
from calendar import monthrange
from datetime import date
from decimal import Decimal

from app.services.ledger import replay
from app.services.portfolio_math import money


def matches(
    condition: str, value: Decimal, since: date | None = None, day: date | None = None
) -> bool:
    """金额/天数精确比较，年/月按批次日期的实际周年/月计算，不猜365天。"""
    parts = re.split("[，,、]", condition.replace(" ", ""))
    for part in parts:
        match = re.fullmatch(
            r"(大于等于|小于等于|大于|小于)(\d+(?:\.\d+)?)(万元|元|天|日|年|个月|月)", part
        )
        if not match:
            return False
        op, number, unit = match.groups()
        limit = Decimal(number) * (10000 if unit == "万元" else 1)
        actual = value
        if unit in {"年", "个月", "月"}:
            if not since or not day or Decimal(number) != int(Decimal(number)):
                return False
            months = since.year * 12 + since.month - 1 + int(number) * (12 if unit == "年" else 1)
            year, month = divmod(months, 12)
            threshold = date(year, month + 1, min(since.day, monthrange(year, month + 1)[1]))
            actual, limit = Decimal((day - threshold).days), Decimal(0)
        if not {
            "大于等于": actual >= limit,
            "小于等于": actual <= limit,
            "大于": actual > limit,
            "小于": actual < limit,
        }[op]:
            return False
    return bool(parts)


def fee_for(
    rules: list[dict[str, str]],
    kind: str,
    value: Decimal,
    gross: Decimal,
    platform: str,
    since: date | None = None,
    day: date | None = None,
) -> tuple[Decimal, dict] | None:
    rows = [
        row for row in rules if row["kind"] == kind and matches(row["condition"], value, since, day)
    ]
    if len(rows) != 1:
        return None
    rule = rows[0]
    discounted = platform == "天天基金" and bool(rule.get("discounted"))
    raw = rule["discounted"] if discounted else rule["standard"]
    percent = re.fullmatch(r"(\d+(?:\.\d+)?)%", raw)
    fixed = re.fullmatch(r"每笔(\d+(?:\.\d+)?)元", raw)
    if percent:
        rate = Decimal(percent[1]) / 100
        fee = money(gross - gross / (1 + rate)) if kind == "buy" else money(gross * rate)
    elif fixed and kind == "buy":
        fee = Decimal(fixed[1])
    else:
        return None
    return fee, {
        "condition": rule["condition"],
        "rate": raw,
        "rate_type": "天天基金公开优惠费率" if discounted else "公开标准费率",
    }


def fifo_lots(rows: list, platform: str, flows: list | None = None, until: date | None = None):
    """按日期重建剩余批次（含拆分/再投/转入），持有期优先从平台确认日算。

    与主账本共用 `ledger.replay`：拆分会按比例作用于批次，
    再投/转入会新增批次，卖出按先进先出消耗，避免费率档位与持仓口径不一致。

    `until` 必须是这笔卖出的定价日：早于卖出日之后的公司行为不能参与，
    否则"未来"的一次转换会把老批次吃掉，历史卖出的持有期档位被改高。
    """
    state = replay(rows, flows or [], until=until, platform=platform)
    if state.shortfall > 0:
        return []

    basis_by_id: dict[int, str] = {}
    for row in rows:
        if row.kind != "buy" or row.status != "confirmed":
            continue
        predicted = (getattr(row, "calculation_basis", None) or {}).get("expected_confirm_on")
        basis_by_id[row.id] = (
            "平台确认日"
            if row.settled_on
            else "公开确认规则推算"
            if predicted
            else "净值日，平台确认日未提供"
        )

    return [
        {
            "id": lot.source_id,
            "shares": lot.shares,
            "since": lot.since or lot.opened_on,
            "date_basis": basis_by_id.get(lot.source_id or 0, "红利再投 / 转入批次"),
        }
        for lot in state.lots
        if lot.shares > 0
    ]


def redemption_fee(
    rules: list,
    rows: list,
    shares: Decimal,
    day: date,
    nav: Decimal,
    platform: str,
    flows: list | None = None,
):
    left, total, details = shares, Decimal(0), []
    for lot in fifo_lots(rows, platform, flows, until=day):
        used = min(left, lot["shares"])
        days = (day - lot["since"]).days
        if days < 0:
            return None
        quote = fee_for(
            rules, "sell", Decimal(days), money(used * nav), platform, lot["since"], day
        )
        if quote is None:
            return None
        fee, rule = quote
        total += fee
        details.append(
            {
                **rule,
                "shares": str(used),
                "days": days,
                "buy_id": lot["id"],
                "date_basis": lot["date_basis"],
                "fee": str(fee),
            }
        )
        left -= used
        if left == 0:
            return money(total), details
    return None
