"""门户 - 基金筛选与详情（公开接口，无需登录）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import RequestIdDep, SessionDep
from app.schemas.common import ApiResponse, PageResult
from app.schemas.fund import (
    FilterOptions,
    FundDetail,
    FundListItem,
    FundQuery,
    HoldingsResult,
    MetricRead,
    NavPointRead,
    NavRange,
)
from app.services.fund import FundService

router = APIRouter(prefix="/funds", tags=["门户 · 基金"])


@router.get("", summary="基金筛选排行", response_model=ApiResponse[PageResult[FundListItem]])
async def list_funds(
    session: SessionDep,
    request_id: RequestIdDep,
    query: Annotated[FundQuery, Query()],
) -> ApiResponse[PageResult[FundListItem]]:
    """按条件筛选基金，支持按区间收益 / 夏普 / 回撤 / 规模排序。

    收益类数据来自数据源的排行接口，风险指标由采集任务逐只补齐；
    未补齐的基金在排序时统一排在末尾（NULL 后置）。
    """
    result = await FundService(session).search(query)
    return ApiResponse(data=result, request_id=request_id)


@router.get("/filters", summary="筛选项字典", response_model=ApiResponse[FilterOptions])
async def filter_options(
    session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[FilterOptions]:
    """前端下拉框数据源，避免在页面里硬编码枚举。"""
    data = await FundService(session).filter_options()
    return ApiResponse(data=data, request_id=request_id)


@router.get("/{code}", summary="基金详情", response_model=ApiResponse[FundDetail])
async def fund_detail(
    code: str, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[FundDetail]:
    data = await FundService(session).detail(code)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/{code}/metrics", summary="基金各区县指标", response_model=ApiResponse[list[MetricRead]]
)
async def fund_metrics(
    code: str, session: SessionDep, request_id: RequestIdDep
) -> ApiResponse[list[MetricRead]]:
    data = await FundService(session).metrics(code)
    return ApiResponse(data=data, request_id=request_id)


@router.get("/{code}/navs", summary="基金净值序列", response_model=ApiResponse[list[NavPointRead]])
async def fund_navs(
    code: str,
    session: SessionDep,
    request_id: RequestIdDep,
    period: Annotated[NavRange, Query(description="时间区间")] = NavRange.Y1,
    limit: Annotated[int, Query(ge=30, le=2000, description="返回点数上限，超出时等距抽样")] = 800,
) -> ApiResponse[list[NavPointRead]]:
    """按时间区间返回净值序列，供详情页曲线使用。

    本地没有数据时会实时回填一次（首次访问约 1 秒，之后走本地）。
    """
    data = await FundService(session).ensure_navs(code, period, limit)
    return ApiResponse(data=data, request_id=request_id)


@router.get(
    "/{code}/holdings", summary="基金季度重仓股", response_model=ApiResponse[HoldingsResult]
)
async def fund_holdings(
    code: str,
    session: SessionDep,
    request_id: RequestIdDep,
    quarter: Annotated[
        str | None, Query(description="季度，如 2025Q2；缺省取最新披露季度")
    ] = None,
) -> ApiResponse[HoldingsResult]:
    """季度重仓股明细（季报数据，占净值比例降序）。

    本地没有数据时会实时回填一次；债券/货币基金通常无股票持仓，返回空列表。
    """
    data = await FundService(session).holdings(code, quarter)
    return ApiResponse(data=data, request_id=request_id)
