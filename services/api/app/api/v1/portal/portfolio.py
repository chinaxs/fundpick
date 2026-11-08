"""门户模拟交易与持仓；所有数据由 CurrentUser 隔离。"""

import csv
import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, RequestIdDep, SessionDep
from app.repositories.transaction import TransactionRepository
from app.schemas.common import ApiResponse, MessageResponse, PageResult
from app.schemas.portfolio import (
    ApplicationInput,
    ApplicationRead,
    AutoTradeInput,
    AutoTradeRead,
    PortfolioRead,
    TradeConfirm,
    TradeHistoryItem,
    TradeHistoryQuery,
    TradeInput,
    TradePreview,
    TradeRead,
    TradeTimingInput,
    TradeTimingRead,
    TradeVoid,
)
from app.schemas.portfolio_tools import (
    FlowCreate,
    FlowRead,
    ImportRequest,
    ImportResult,
    ReconciliationResult,
)
from app.services.automatic_trade import AutomaticTradeService
from app.services.portfolio import PortfolioService
from app.services.portfolio_provenance import PortfolioProvenanceService
from app.services.portfolio_tools import PortfolioToolsService
from app.services.trade_application import ApplicationService
from app.services.trade_history import TradeHistoryService
from app.services.trade_timing import timing
from app.services.transaction import TransactionService

router = APIRouter(prefix="/me", tags=["门户 · 会员中心（需登录）"])


@router.get("/holding-codes", response_model=ApiResponse[list[str]], summary="已持仓基金代码")
async def holding_codes(user: CurrentUser, session: SessionDep, request_id: RequestIdDep):
    data = await PortfolioService(session).held_codes(user.id)
    return ApiResponse(data=data, request_id=request_id)


@router.get("/portfolio", response_model=ApiResponse[PortfolioRead], summary="交易汇总持仓")
async def portfolio(user: CurrentUser, session: SessionDep, request_id: RequestIdDep):
    data = await PortfolioService(session).overview(user.id)
    return ApiResponse(data=data, request_id=request_id)


@router.post(
    "/transactions/preview", response_model=ApiResponse[TradePreview], summary="预览模拟买卖"
)
async def preview(
    payload: TradeInput, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    data = await TransactionService(session).preview(user.id, payload)
    return ApiResponse(data=data, request_id=request_id)


@router.post("/transactions", response_model=ApiResponse[TradeRead], summary="确认模拟买卖")
async def confirm(
    payload: TradeConfirm, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    data = await TransactionService(session).confirm(user.id, payload)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/records",
    response_model=ApiResponse[PageResult[TradeHistoryItem]],
    summary="统一交易记录筛选与分页",
)
async def transactions(
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
    query: Annotated[TradeHistoryQuery, Query()],
):
    data = await TradeHistoryService(session).list(user.id, query)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/transactions",
    response_model=ApiResponse[PageResult[TradeRead]],
    summary="成交流水（兼容接口，统一筛选记录请使用records）",
)
async def legacy_transactions(
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    data = await TransactionService(session).list(user.id, page, page_size)
    return ApiResponse(data=data, request_id=request_id)


@router.post(
    "/transactions/{transaction_id}/void",
    response_model=ApiResponse[TradeRead],
    summary="作废最后一笔有效交易",
)
async def void(
    transaction_id: int,
    payload: TradeVoid,
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
):
    data = await TransactionService(session).void(user.id, transaction_id, payload.reason)
    return ApiResponse(data=data, request_id=request_id)


@router.post(
    "/transactions/timing",
    response_model=ApiResponse[TradeTimingRead],
    summary="校验申请时间与净值所属日",
)
async def trade_timing(
    payload: TradeTimingInput, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    data = await timing(TransactionRepository(session), payload)
    return ApiResponse(data=data, request_id=request_id)


@router.post(
    "/applications", response_model=ApiResponse[ApplicationRead], summary="保存待确认申请记录"
)
async def save_application(
    payload: ApplicationInput, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    data = await ApplicationService(session).create(user.id, payload)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/applications", response_model=ApiResponse[list[ApplicationRead]], summary="待确认申请"
)
async def applications(user: CurrentUser, session: SessionDep, request_id: RequestIdDep):
    user_id = user.id
    await AutomaticTradeService(session).refresh_pending(user_id)
    data = await ApplicationService(session).list(user_id)
    return ApiResponse(data=data, request_id=request_id)


@router.post(
    "/applications/{application_id}/cancel",
    response_model=ApiResponse[MessageResponse],
    summary="取消本地待确认记录",
)
async def cancel_application(
    application_id: int, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    await ApplicationService(session).cancel(user.id, application_id)
    return ApiResponse(
        data=MessageResponse(message="本地记录已取消，请另行处理实际平台申请"),
        request_id=request_id,
    )


@router.post(
    "/auto-transactions",
    response_model=ApiResponse[AutoTradeRead],
    summary="按时间金额自动查询并记账",
)
async def automatic_trade(
    payload: AutoTradeInput, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    data = await AutomaticTradeService(session).save(user.id, payload)
    return ApiResponse(data=data, request_id=request_id)


@router.delete(
    "/transactions/{transaction_id}",
    response_model=ApiResponse[MessageResponse],
    summary="删除已作废交易记录",
)
async def delete_transaction(
    transaction_id: int, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    await TradeHistoryService(session).delete(user.id, "transaction", transaction_id)
    return ApiResponse(data=MessageResponse(message="记录已删除"), request_id=request_id)


@router.delete(
    "/applications/{application_id}",
    response_model=ApiResponse[MessageResponse],
    summary="删除已撤销申请记录",
)
async def delete_application(
    application_id: int, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
):
    await TradeHistoryService(session).delete(user.id, "application", application_id)
    return ApiResponse(data=MessageResponse(message="记录已删除"), request_id=request_id)


# ---------------------------------------------------------------- 持仓工具
@router.post(
    "/portfolio/import",
    response_model=ApiResponse[ImportResult],
    summary="导入历史持仓（从零开始）",
)
async def import_positions(
    payload: ImportRequest, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[ImportResult]:
    """把已有持仓按买入流水导入。

    只用于该基金还没有任何记录的情况：否则同一段历史会被记两遍。
    `dry_run=true` 时只校验并返回将导入的内容，前端用于预览。
    """
    result = await PortfolioToolsService(session).import_positions(user.id, payload)
    return ApiResponse(
        code=0,
        message="导入完成" if not payload.dry_run else "校验通过",
        data=result,
        request_id=request_id,
    )


@router.get(
    "/portfolio/flows",
    response_model=ApiResponse[list[FlowRead]],
    summary="分红/拆分/转换流水",
)
async def list_flows(
    user: CurrentUser,
    session: SessionDep,
    request_id: RequestIdDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[FlowRead]]:
    rows = await PortfolioToolsService(session).list_flows(user.id, limit)
    return ApiResponse(data=rows, request_id=request_id)


@router.post(
    "/portfolio/flows",
    response_model=ApiResponse[FlowRead],
    status_code=201,
    summary="记录公司行为",
)
async def create_flow(
    payload: FlowCreate, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[FlowRead]:
    flow = await PortfolioToolsService(session).add_flow(user.id, payload)
    return ApiResponse(code=0, message="已记录", data=flow, request_id=request_id)


@router.delete("/portfolio/flows/{flow_id}", response_model=ApiResponse[MessageResponse])
async def delete_flow(
    flow_id: int, user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[MessageResponse]:
    await PortfolioToolsService(session).delete_flow(user.id, flow_id)
    return ApiResponse(data=MessageResponse(message="已删除"), request_id=request_id)


@router.get(
    "/portfolio/reconciliation",
    response_model=ApiResponse[ReconciliationResult],
    summary="收益核对",
)
async def reconcile(
    user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[ReconciliationResult]:
    data = await PortfolioToolsService(session).reconcile(user.id)
    return ApiResponse(data=data, request_id=request_id)


@router.get("/portfolio/export", summary="导出交易与公司行为流水（CSV）")
async def export_portfolio(user: CurrentUser, session: SessionDep) -> Response:
    rows = await PortfolioToolsService(session).export_rows(user.id)
    headers = [
        ("type", "记录类型"),
        ("date", "日期"),
        ("code", "基金代码"),
        ("name", "基金名称"),
        ("kind", "方向/事件"),
        ("quantity", "份额"),
        ("nav", "净值"),
        ("amount", "金额"),
        ("fee", "费用"),
        ("cash", "现金流"),
        ("status", "状态"),
        ("source", "来源"),
        ("note", "备注"),
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in headers])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in headers])
    # BOM 让 Excel 正确识别 UTF-8
    content = "\ufeff" + buffer.getvalue()
    filename = f"portfolio-{user.username}-{date.today().isoformat()}.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/portfolio/ai-context",
    summary="账本快照（供 AI 使用，带来源与确认状态）",
)
async def ai_context(
    user: CurrentUser, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[dict]:
    """把账本整理成"可被模型安全引用"的结构。

    每条记录都带 `confidence`：receipt 才是平台回执；estimated/calculated 是
    系统推算；pending 是待确认申请；legacy 是迁移前的旧估算。
    模型只能按这个口径描述，不能把预计说成已确认。
    """
    data = await PortfolioProvenanceService(session).build(user.id)
    return ApiResponse(data=data, request_id=request_id)
