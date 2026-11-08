"""给 AI 用的账本快照：每条记录都带来源与确认状态。

为什么单独做一层而不是让模型直接读库：

- 模型无法判断 `record_source=estimated` 与 `receipt` 的差别，
  而这两者的可信度完全不同（前者是系统按公开费率推算，后者是平台回执）；
- 待确认申请、已作废旧记录、旧版估算持仓必须**分开列示**，
  混在一起会让模型把"预计"说成"已确认"；
- 修正链（作废原因、来源申请、旧持仓迁移）要显式给出，模型才能解释差异。

输出是纯数据结构（dict），不承诺稳定给前端复用；接口与工具共用同一份实现。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.models.fund_position import FundPosition
from app.models.fund_transaction import FundTransaction
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.trade_application import TradeApplication
from app.models.user import User
from app.services.ledger import replay

# 记录可信度：AI 必须按这个口径描述，不得自行升级
CONFIDENCE_LABELS: dict[str, str] = {
    "receipt": "平台回执确认",
    "estimated": "系统估算（未与平台对账）",
    "calculated": "系统计算（按公开费率）",
    "import": "用户导入的历史记录",
    "legacy": "旧版估算持仓（未迁移）",
}

EVIDENCE_NOTES = [
    "只有「平台回执确认」的记录可以直接当作成交事实引用。",
    "「系统估算」「系统计算」是按公开净值与费率推算的，实际以平台为准。",
    "「待确认」是已提交但还没有回执的申请，不能计入已实现收益或可卖份额。",
    "「旧版估算持仓」来自迁移前的数据模型，只保留原值，尚未与新账本核对。",
]


@dataclass
class _FundRows:
    """按基金聚合的流水与公司行为（重放前的最小上下文）。"""

    code: str
    name: str
    rows: list = field(default_factory=list)
    flows: list = field(default_factory=list)
    last_day: date | None = None


def _money(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _confidence(record_source: str) -> str:
    if record_source in CONFIDENCE_LABELS:
        return record_source
    return "calculated"


class PortfolioProvenanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(self, user_id: int) -> dict[str, object]:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ValueError("会员不存在")

        transactions = (
            await self.session.execute(
                select(FundTransaction, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundTransaction.fund_id)
                .where(
                    FundTransaction.user_id == user_id,
                    FundTransaction.deleted_at.is_(None),
                )
                .order_by(FundTransaction.confirmed_on, FundTransaction.id)
            )
        ).all()
        applications = (
            await self.session.execute(
                select(TradeApplication, Fund.code, Fund.name)
                .join(Fund, Fund.id == TradeApplication.fund_id)
                .where(
                    TradeApplication.user_id == user_id,
                    TradeApplication.status == "pending",
                    TradeApplication.deleted_at.is_(None),
                )
                .order_by(TradeApplication.submitted_at)
            )
        ).all()
        legacy = (
            await self.session.execute(
                select(FundPosition, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundPosition.fund_id)
                .where(
                    FundPosition.user_id == user_id,
                    FundPosition.deleted_at.is_(None),
                )
            )
        ).all()
        flows = (
            await self.session.execute(
                select(FundPortfolioFlow, Fund.code, Fund.name)
                .join(Fund, Fund.id == FundPortfolioFlow.fund_id)
                .where(
                    FundPortfolioFlow.user_id == user_id,
                    FundPortfolioFlow.deleted_at.is_(None),
                )
                .order_by(FundPortfolioFlow.effective_on)
            )
        ).all()

        records = []
        counters: dict[str, int] = {}
        for tx, code, name in transactions:
            status = "voided" if tx.voided_at is not None else tx.status
            confidence = _confidence(tx.record_source)
            counters[confidence] = counters.get(confidence, 0) + 1
            records.append(
                {
                    "id": tx.id,
                    "code": code,
                    "name": name,
                    "kind": tx.kind,
                    "status": status,
                    "confidence": confidence,
                    "confidence_label": CONFIDENCE_LABELS.get(confidence, confidence),
                    "platform": tx.platform,
                    "submitted_at": tx.submitted_at.isoformat() if tx.submitted_at else None,
                    "confirmed_on": tx.confirmed_on.isoformat(),
                    "settled_on": tx.settled_on.isoformat() if tx.settled_on else None,
                    "amount": _money(tx.amount),
                    "shares": _money(tx.shares),
                    "nav": _money(tx.nav),
                    "nav_source": tx.nav_source,
                    "fee": _money(tx.fee),
                    "cash_amount": _money(tx.cash_amount),
                    "realized_profit": _money(tx.realized_profit),
                    "provenance": {
                        "record_source": tx.record_source,
                        "pricing_rule": tx.pricing_rule,
                        "application_id": tx.application_id,
                        "legacy_position_id": tx.legacy_position_id,
                        "request_key": tx.request_key,
                        "receipt_ref": tx.receipt_ref,
                        "calculation_basis": tx.calculation_basis,
                    },
                    "correction": (
                        {
                            "voided_at": tx.voided_at.isoformat(),
                            "void_reason": tx.void_reason,
                        }
                        if tx.voided_at is not None
                        else None
                    ),
                }
            )

        pending = [
            {
                "id": application.id,
                "code": code,
                "name": name,
                "kind": application.kind,
                "platform": application.platform,
                "submitted_at": application.submitted_at.isoformat(),
                "expected_nav_on": (
                    application.expected_nav_on.isoformat() if application.expected_nav_on else None
                ),
                "amount": _money(application.amount),
                "shares": _money(application.shares),
                "status": "pending",
                "confidence": "pending",
                "confidence_label": "待确认（尚无回执）",
                "processing_message": application.processing_message,
            }
            for application, code, name in applications
        ]

        legacy_positions = [
            {
                "id": position.id,
                "code": code,
                "name": name,
                "amount": _money(position.amount),
                "cost_nav": _money(position.cost_nav),
                "bought_at": position.bought_at.isoformat(),
                "nav_source": position.nav_source,
                "confidence": "legacy",
                "confidence_label": CONFIDENCE_LABELS["legacy"],
            }
            for position, code, name in legacy
        ]

        flow_rows = [
            {
                "id": flow.id,
                "code": code,
                "name": name,
                "kind": flow.kind,
                "effective_on": flow.effective_on.isoformat(),
                "cash_amount": _money(flow.cash_amount),
                "shares_delta": _money(flow.shares_delta),
                "ratio": _money(flow.ratio),
                "platform": flow.platform,
                "note": flow.note,
                "confidence": "manual",
                "confidence_label": "用户手工记录（需与平台核对）",
            }
            for flow, code, name in flows
        ]

        # 持仓快照与持仓页、费率计算共用同一套重放：模型不能直接读流水行上的
        # remaining_shares（那是确认当时的快照，补录拆分后会过期）。
        positions = self._positions(transactions, flows)

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "member": {"id": user.id, "username": user.username},
            "summary": {
                "receipt": counters.get("receipt", 0),
                "estimated": counters.get("estimated", 0) + counters.get("calculated", 0),
                "imported": counters.get("import", 0),
                "pending": len(pending),
                "legacy": len(legacy_positions),
                "flows": len(flow_rows),
            },
            "positions": positions,
            "records": records,
            "pending": pending,
            "legacy": legacy_positions,
            "flows": flow_rows,
            "notes": EVIDENCE_NOTES,
        }

    @staticmethod
    def _positions(transactions: Sequence, flows: Sequence) -> list[dict[str, object]]:
        """按基金汇总重放结果；只出现在公司行为里的基金也会列出来。"""
        grouped: dict[int, _FundRows] = {}
        for tx, code, name in transactions:
            entry = grouped.setdefault(tx.fund_id, _FundRows(code=code, name=name))
            if tx.status == "confirmed" and tx.voided_at is None:
                entry.rows.append(tx)
            if entry.last_day is None or tx.confirmed_on > entry.last_day:
                entry.last_day = tx.confirmed_on
        for flow, code, name in flows:
            entry = grouped.setdefault(flow.fund_id, _FundRows(code=code, name=name))
            entry.flows.append(flow)
            if entry.last_day is None or flow.effective_on > entry.last_day:
                entry.last_day = flow.effective_on

        positions: list[dict[str, object]] = []
        for entry in sorted(grouped.values(), key=lambda item: item.code):
            state = replay(entry.rows, entry.flows)
            if state.shares <= 0 and not state.bought:
                continue
            positions.append(
                {
                    "code": entry.code,
                    "name": entry.name,
                    "shares": _money(state.shares),
                    "cost": _money(state.cost),
                    "average_cost": _money(state.average_cost),
                    "realized_profit": _money(state.realized),
                    "dividends": _money(state.dividends),
                    "platform_shares": {
                        key: _money(value) for key, value in state.platform_shares.items()
                    },
                    "last_event_on": entry.last_day.isoformat() if entry.last_day else None,
                }
            )
        return positions
