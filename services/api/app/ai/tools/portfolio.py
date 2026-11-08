"""持仓类工具：只读，且必须带上来源与确认状态。

工具不知道调用者是谁——`user_id` 由入口层（HTTP 依赖或智能体上下文）
按登录身份注入。工具内部不做权限判断，也**不提供任何写操作**：
金额与份额的更正必须回到会员自己的确认流程。
"""

from __future__ import annotations

import json
from typing import Any, cast

from langchain_core.tools import tool

from app.db.session import async_session_factory
from app.services.portfolio_provenance import PortfolioProvenanceService


@tool
async def portfolio_evidence(user_id: int, limit: int = 20) -> str:
    """读取指定会员的账本快照，用于解释"这笔钱怎么来的"。

    返回的每条记录都带 confidence 字段：receipt=平台回执确认，
    estimated/calculated=系统按公开净值与费率推算，pending=待确认申请，
    legacy=迁移前的旧估算。引用数字时必须说明属于哪一种，不得混用。

    Args:
        user_id: 会员 ID，由入口层按登录身份注入，不能由模型自行猜测。
        limit: 最多返回多少条已确认记录，1-50。
    """
    size = max(1, min(int(limit), 50))
    async with async_session_factory() as session:
        snapshot = await PortfolioProvenanceService(session).build(int(user_id))

    records = cast("list[dict[str, Any]]", snapshot["records"])
    positions = cast("list[dict[str, Any]]", snapshot["positions"])
    payload = {
        "member": snapshot["member"],
        "summary": snapshot["summary"],
        # 持仓来自统一账本重放，和持仓页、费率计算同一份结果
        "positions": positions,
        "records": records[-size:],
        "pending": snapshot["pending"],
        "legacy": snapshot["legacy"],
        "flows": snapshot["flows"],
        "notes": snapshot["notes"],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["portfolio_evidence"]
