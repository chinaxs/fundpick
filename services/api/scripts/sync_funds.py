"""基金数据同步脚本。

用法：
    uv run python -m scripts.sync_funds --mode quick      # 公司/基金/经理/排行（先跑这个）
    uv run python -m scripts.sync_funds --mode risk --limit 500  # 风险指标（逐只，可分批）
    uv run python -m scripts.sync_funds --mode navs --limit 100  # 净值序列（详情页图表用）
    uv run python -m scripts.sync_funds --mode detail --limit 500  # 档案+真实费率
    uv run python -m scripts.sync_funds --mode holdings --limit 100  # 季度重仓股
    uv run python -m scripts.sync_funds --mode detail --codes 021180  # 只补指定基金

设计要点：
- 所有写入按 500 条一批 upsert（MySQL ON DUPLICATE KEY UPDATE），避免先查后插；
- 数据源调用是同步阻塞的，用 asyncio.to_thread 隔离，不阻塞事件循环；
- 每个模式可单独执行、可重复执行（幂等），失败后重跑不会产生脏数据；
- 费率（管理费/托管费）只写拿到的真实值，拿不到保持 NULL——绝不写 0 兜底。
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, setup_logging
from app.datasources import RANK_CATEGORIES, get_provider
from app.datasources.base import FundSnapshot
from app.db.session import async_session_factory, dispose_engine
from app.models import (
    Fund,
    FundCompany,
    FundManager,
    FundMetric,
    FundNav,
    FundType,
)

logger = get_logger("sync_funds")
BATCH = 500
STARTED_AT = time.time()
_EMPTY_TOKENS = {"", "---", "--", "nan", "NaN", "NaT", "None", "null"}


# ---------------------------------------------------------------- 工具
def _elapsed() -> str:
    return f"{time.time() - STARTED_AT:.0f}s"


def match_company(short_name: str, companies: dict[str, int]) -> int | None:
    """把经理表的公司简称匹配到公司表的全称。

    数据源口径不一致：公司表是"华夏基金管理有限公司"，经理表是"华夏基金"。
    先精确匹配，再按前缀匹配（简称是全称的前缀）。
    """
    if not short_name:
        return None
    if short_name in companies:
        return companies[short_name]
    for full_name, company_id in companies.items():
        if full_name.startswith(short_name):
            return company_id
    return None


def to_num(value: Any) -> float | None:
    """转 float，NaN / 空值 / 非法值统一返回 None（MySQL 不接受 NaN）。"""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return None if num != num else num


def map_fund_type(raw_type: str) -> FundType:
    """把数据源的细分类型（如"混合型-灵活"）归一到自家枚举。"""
    raw = raw_type or ""
    if "QDII" in raw.upper():
        return FundType.QDII
    if "FOF" in raw.upper():
        return FundType.FOF
    if "指数" in raw:
        return FundType.INDEX
    if raw.startswith("股票型"):
        return FundType.STOCK
    if raw.startswith("混合型"):
        return FundType.HYBRID
    if raw.startswith("债券型"):
        return FundType.BOND
    if raw.startswith("货币型"):
        return FundType.MONEY
    return FundType.OTHER


def chunks(items: Sequence[Any], size: int = BATCH) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def upsert(
    session: AsyncSession, model: Any, rows: list[dict[str, Any]], keys: list[str]
) -> int:
    """批量 upsert，返回处理条数。keys 是需要更新的字段（不含主键/唯一键）。"""
    if not rows:
        return 0
    total = 0
    for batch in chunks(rows):
        stmt = insert(model).values(list(batch))
        if keys:
            stmt = stmt.on_duplicate_key_update(**{k: stmt.inserted[k] for k in keys})
        else:
            # 无需更新的表（如公司）遇到重复直接跳过
            stmt = stmt.prefix_with("IGNORE")
        await session.execute(stmt)
        total += len(batch)
    await session.commit()
    return total


# ---------------------------------------------------------------- 各阶段
async def sync_companies(session: AsyncSession) -> dict[str, int]:
    """基金公司：来自规模排行接口，一次拿全量。"""
    df_rows = await asyncio.to_thread(_load_company_rows)
    if not df_rows:
        return {}

    existing = dict((await session.execute(select(FundCompany.name, FundCompany.id))).all())
    new_rows = [{"name": r["name"]} for r in df_rows if r["name"] and r["name"] not in existing]
    if new_rows:
        await upsert(session, FundCompany, new_rows, [])
        existing = dict((await session.execute(select(FundCompany.name, FundCompany.id))).all())
    logger.info("[公司] 共 %d 家，新增 %d（%s）", len(existing), len(new_rows), _elapsed())
    return existing


def _load_company_rows() -> list[dict[str, str]]:
    import akshare as ak

    df = ak.fund_aum_em()
    return [{"name": str(n).strip()} for n in df.get("基金公司", [])]


async def sync_managers(
    session: AsyncSession, company_ids: dict[str, int]
) -> dict[tuple[str, str], int]:
    """基金经理 + 经理-基金关系。"""
    rows = await asyncio.to_thread(_load_manager_rows)
    if not rows:
        return {}

    # (name, company_name) 去重，保留一条汇总信息
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["name"], r["company"])
        if key not in unique:
            unique[key] = r

    payload = [
        {
            "name": name,
            "company_id": match_company(company, company_ids),
            "tenure_years": r["tenure_days"] / 365 if r["tenure_days"] else None,
            "managed_scale": r["scale"],
            "best_return": r["best_return"],
        }
        for (name, company), r in unique.items()
    ]
    # 唯一约束是 (name, company_id)，但 company_id 可能为 NULL（匹配不到公司），
    # MySQL 允许多个 NULL 共存，会导致同一经理每次同步都被重复插入。
    # 因此改为按 name 做"存在则更新、不存在则插入"。
    from sqlalchemy import update

    existing_managers = dict(
        (await session.execute(select(FundManager.name, FundManager.id))).all()
    )
    to_insert = [item for item in payload if item["name"] not in existing_managers]
    if to_insert:
        await upsert(
            session,
            FundManager,
            to_insert,
            ["company_id", "tenure_years", "managed_scale", "best_return"],
        )

    for item in payload:
        manager_id = existing_managers.get(item["name"])
        if manager_id is None:
            continue
        values = {k: v for k, v in item.items() if k != "name"}
        await session.execute(
            update(FundManager).where(FundManager.id == manager_id).values(**values)
        )
    await session.commit()

    manager_ids = {
        (name, cid): mid
        for name, cid, mid in (
            await session.execute(select(FundManager.name, FundManager.company_id, FundManager.id))
        ).all()
    }
    logger.info("[经理] 去重后 %d 人（%s）", len(unique), _elapsed())

    return {
        (name, company): manager_ids[(name, cid)]
        for (name, company) in unique
        if (cid := match_company(company, company_ids)) is not None and (name, cid) in manager_ids
    }


def _load_manager_rows() -> list[dict[str, Any]]:
    import akshare as ak

    df = ak.fund_manager_em()
    out: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        name = str(getattr(row, "姓名", "")).strip()
        if not name:
            continue
        tenure = getattr(row, "累计从业时间", None)
        out.append(
            {
                "name": name,
                "company": str(getattr(row, "所属公司", "")).strip(),
                "code": str(getattr(row, "现任基金代码", "")).strip(),
                "tenure_days": to_num(tenure),
                "scale": to_num(getattr(row, "现任基金资产总规模", None)),
                "best_return": to_num(getattr(row, "现任基金最佳回报", None)),
            }
        )
    return out


async def sync_funds(session: AsyncSession) -> int:
    """基金基础列表。"""
    basics = await asyncio.to_thread(_load_fund_basics)
    payload = [
        {
            "code": b["code"],
            "name": b["name"],
            "type": map_fund_type(b["raw_type"]),
            "full_name": None,
        }
        for b in basics
    ]
    total = await upsert(session, Fund, payload, ["name", "type"])
    logger.info("[基金] 基础信息 %d 条（%s）", total, _elapsed())
    return total


def _load_fund_basics() -> list[dict[str, str]]:
    provider = get_provider()
    return [{"code": f.code, "name": f.name, "raw_type": f.raw_type} for f in provider.list_funds()]


async def sync_snapshots(session: AsyncSession) -> int:
    """各类型排行快照：补齐最新净值、费率，并写入区间收益指标。"""
    provider = get_provider()
    snapshots: list[FundSnapshot] = []
    for category in RANK_CATEGORIES:
        try:
            rows = await asyncio.to_thread(provider.list_snapshots, category)
            snapshots.extend(rows)
            logger.info("[排行] %s %d 条", category, len(rows))
        except Exception as exc:  # 单个分类失败不影响整体
            logger.warning("[排行] %s 失败：%s", category, exc)

    if not snapshots:
        return 0

    code_to_id = dict((await session.execute(select(Fund.code, Fund.id))).all())

    fund_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    period_map = {
        "1w": "return_1w",
        "1m": "return_1m",
        "3m": "return_3m",
        "6m": "return_6m",
        "1y": "return_1y",
        "2y": "return_2y",
        "3y": "return_3y",
        "ytd": "return_ytd",
        "all": "return_all",
    }

    for s in snapshots:
        fid = code_to_id.get(s.code)
        if fid is None:
            continue
        fund_rows.append(
            {
                "code": s.code,
                "name": s.name,
                "latest_nav": s.unit_nav,
                "latest_nav_date": s.nav_date,
            }
        )
        for period, attr in period_map.items():
            value = getattr(s, attr, None)
            if value is None:
                continue
            metric_rows.append(
                {
                    "fund_id": fid,
                    "period": period,
                    "nav_date": s.nav_date,
                    "return_rate": value,
                }
            )

    # 注意：不把排行接口的"手续费"（申购费）写进 management_fee。
    # 管理费/托管费是按年计提的费率，来自 fund_profile 的费用明细（sync_details）。
    await upsert(session, Fund, fund_rows, ["name", "latest_nav", "latest_nav_date"])
    updated = await upsert(session, FundMetric, metric_rows, ["nav_date", "return_rate"])
    logger.info("[快照] 基金 %d 条，指标 %d 条（%s）", len(fund_rows), updated, _elapsed())
    return updated


async def sync_risks(session: AsyncSession, limit: int | None) -> int:
    """风险指标：逐只拉取，写入 1y/3y/5y 的波动率、夏普、最大回撤。"""
    # 优先补给"有区间收益数据"的基金；同时跳过已采过的，便于分批续跑
    done = select(FundMetric.fund_id).where(FundMetric.sharpe.is_not(None))
    funds = (
        await session.execute(
            select(Fund.id, Fund.code)
            .join(FundMetric, FundMetric.fund_id == Fund.id)
            .where(
                Fund.deleted_at.is_(None),
                FundMetric.period == "1y",
                Fund.id.not_in(done),
            )
            .distinct()
            .order_by(Fund.id)
        )
    ).all()
    if limit:
        funds = funds[:limit]

    provider = get_provider()
    done = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        try:
            rows = await asyncio.to_thread(provider.risk_metrics, code)
        except Exception as exc:
            logger.debug("[风险] %s 失败：%s", code, exc)
            continue

        payload = []
        for r in rows:
            payload.append(
                {
                    "fund_id": fund_id,
                    "period": r.period,
                    "volatility": r.volatility,
                    "sharpe": r.sharpe,
                    "max_drawdown": r.max_drawdown,
                }
            )
        if payload:
            await upsert(session, FundMetric, payload, ["volatility", "sharpe", "max_drawdown"])
            done += 1

        if idx % 100 == 0:
            logger.info("[风险] %d/%d 已处理（%s）", idx, len(funds), _elapsed())
        await asyncio.sleep(0.05)  # 轻微限速，避免触发反爬

    logger.info("[风险] 完成 %d 只（%s）", done, _elapsed())
    return done


async def sync_details(session: AsyncSession, limit: int | None, codes: list[str] | None) -> int:
    """补全基金档案：全称、规模、成立日期、管理费/托管费。

    费率必须来自雪球的费用明细（按年计提），排行接口的"手续费"是申购费，
    两者语义完全不同（C 类申购费为 0，曾被误当管理费写入）。
    """
    from sqlalchemy import or_, update

    if codes:
        funds = (
            await session.execute(
                select(Fund.id, Fund.code).where(Fund.code.in_(codes))
            )
        ).all()
    else:
        # 逐只请求（约 0.3 秒/只），按近一年收益降序，优先补用户最常看到的头部基金。
        # MySQL 不支持 NULLS LAST，用 "IS NULL 升序 + 收益降序" 等价实现
        stmt = (
            select(Fund.id, Fund.code)
            .outerjoin(FundMetric, (FundMetric.fund_id == Fund.id) & (FundMetric.period == "1y"))
            .where(
                Fund.deleted_at.is_(None),
                or_(
                    Fund.scale.is_(None),
                    Fund.inception_date.is_(None),
                    Fund.management_fee.is_(None),
                ),
            )
            .order_by(FundMetric.return_rate.is_(None), FundMetric.return_rate.desc(), Fund.id)
        )
        if limit:
            stmt = stmt.limit(limit)
        funds = (await session.execute(stmt)).all()

    provider = get_provider()
    updated = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        try:
            profile = await asyncio.to_thread(provider.fund_profile, code)
        except Exception as exc:
            logger.debug("[档案] %s 失败：%s", code, exc)
            continue
        if profile is None:
            continue

        values: dict[str, Any] = {}
        if profile.scale is not None:
            values["scale"] = profile.scale
        if profile.inception_date is not None:
            values["inception_date"] = profile.inception_date
        if profile.full_name:
            values["full_name"] = profile.full_name
        # 费率只写非 None 值：拿不到就保持 NULL，绝不写 0 兜底
        if profile.management_fee is not None:
            values["management_fee"] = profile.management_fee
        if profile.custody_fee is not None:
            values["custody_fee"] = profile.custody_fee
        if not values:
            continue

        await session.execute(update(Fund).where(Fund.id == fund_id).values(**values))
        updated += 1
        if idx % 50 == 0:
            await session.commit()
            logger.info("[档案] %d/%d 已处理（%s）", idx, len(funds), _elapsed())
        await asyncio.sleep(0.05)

    await session.commit()
    logger.info("[档案] 更新 %d 只（%s）", updated, _elapsed())
    return updated


async def sync_navs(session: AsyncSession, limit: int | None) -> int:
    """净值序列：只拉取已有指标、按浏览次数排序的前 N 只，避免全量拉爆。

    全市场 1 万只 × 数千条 ≈ 千万级行，全量拉取需要数小时；
    详情页需要曲线时再按需补齐更划算。
    """
    stmt = select(Fund.id, Fund.code).where(Fund.deleted_at.is_(None)).order_by(Fund.id)
    if limit:
        stmt = stmt.limit(limit)
    funds = (await session.execute(stmt)).all()

    provider = get_provider()
    total = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        try:
            points = await asyncio.to_thread(provider.nav_history, code)
        except Exception as exc:
            logger.debug("[净值] %s 失败：%s", code, exc)
            continue
        if not points:
            continue

        rows = [
            {
                "fund_id": fund_id,
                "nav_date": p.nav_date,
                "unit_nav": p.unit_nav,
                "daily_return": p.daily_return,
            }
            for p in points
        ]
        total += await upsert(session, FundNav, rows, ["unit_nav", "daily_return"])
        if idx % 50 == 0:
            logger.info("[净值] %d/%d（%s）", idx, len(funds), _elapsed())

    logger.info("[净值] 写入 %d 条（%s）", total, _elapsed())
    return total


async def sync_holdings(session: AsyncSession, limit: int | None, codes: list[str] | None) -> int:
    """季度重仓股：逐只拉取当年披露的各季度前十大重仓。

    按流通市值降序补齐（大盘基金先采），同一季度重复采集幂等覆盖。
    """
    from app.models import FundHolding

    year = str(datetime.now().year)
    if codes:
        funds = (
            await session.execute(select(Fund.id, Fund.code).where(Fund.code.in_(codes)))
        ).all()
    else:
        stmt = (
            select(Fund.id, Fund.code)
            .where(Fund.deleted_at.is_(None), Fund.type.in_(["stock", "hybrid", "index"]))
            .order_by(Fund.scale.is_(None), Fund.scale.desc(), Fund.id)
        )
        if limit:
            stmt = stmt.limit(limit)
        funds = (await session.execute(stmt)).all()

    provider = get_provider()
    total = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        try:
            holdings = await asyncio.to_thread(provider.fund_holdings, code, year)
        except Exception as exc:
            logger.debug("[持仓] %s 失败：%s", code, exc)
            continue
        if not holdings:
            continue

        rows = [
            {
                "fund_id": fund_id,
                "quarter": h.quarter,
                "stock_code": h.stock_code,
                "stock_name": h.stock_name,
                "rank": h.rank or None,
                "ratio": h.ratio,
                "shares": h.shares,
                "market_value": h.market_value,
            }
            for h in holdings
        ]
        total += await upsert(
            session,
            FundHolding,
            rows,
            ["stock_name", "rank", "ratio", "shares", "market_value"],
        )
        if idx % 50 == 0:
            logger.info("[持仓] %d/%d（%s）", idx, len(funds), _elapsed())
        await asyncio.sleep(0.1)  # 重仓接口较重，限速防反爬

    logger.info("[持仓] 写入 %d 条（%s）", total, _elapsed())
    return total


def _load_scale_rows() -> list[dict[str, Any]]:
    """开放式基金规模与成立日期。

    数据源只给"最近总份额"和"单位净值"，规模按 份额 × 净值 换算成亿元；
    总募集规模是发行期数据，不能当当前规模用。
    """
    import akshare as ak

    df = ak.fund_scale_open_sina()
    out: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        code = str(getattr(row, "基金代码", "")).strip()
        if not code:
            continue
        shares = to_num(getattr(row, "最近总份额", None))
        nav = to_num(getattr(row, "单位净值", None))
        scale = round(shares * nav / 1e8, 4) if shares and nav else None
        out.append(
            {
                "code": code,
                "scale": scale,
                "inception_date": _parse_date(getattr(row, "成立日期", None)),
            }
        )
    return out


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    if text in _EMPTY_TOKENS:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


async def sync_scale(session: AsyncSession) -> int:
    """补齐基金规模与成立日期（约 7000 只可覆盖）。

    用 UPDATE 而不是 upsert：INSERT ... ON DUPLICATE 要求提供所有非空字段（如 name），
    而这里只拿到部分字段，逐条 UPDATE 更稳妥。
    """
    from sqlalchemy import update

    rows = await asyncio.to_thread(_load_scale_rows)
    codes = [r["code"] for r in rows if r["scale"] is not None or r["inception_date"] is not None]
    if not codes:
        return 0

    existing = dict(
        (await session.execute(select(Fund.code, Fund.id).where(Fund.code.in_(codes)))).all()
    )

    updated = 0
    for row in rows:
        fund_id = existing.get(row["code"])
        if fund_id is None:
            continue
        values: dict[str, Any] = {}
        if row["scale"] is not None:
            values["scale"] = row["scale"]
        if row["inception_date"] is not None:
            values["inception_date"] = row["inception_date"]
        if not values:
            continue
        await session.execute(update(Fund).where(Fund.id == fund_id).values(**values))
        updated += 1

    await session.commit()
    logger.info("[规模] 更新 %d 只（%s）", updated, _elapsed())
    return updated


async def link_managers(session: AsyncSession, manager_ids: dict[tuple[str, str], int]) -> int:
    """把经理回填到基金的 manager_id（一只基金只留第一位经理）。"""
    rows = await asyncio.to_thread(_load_manager_rows)
    fund_ids = dict((await session.execute(select(Fund.code, Fund.id))).all())

    update_map: dict[int, int] = {}
    for r in rows:
        mid = manager_ids.get((r["name"], r["company"]))
        fid = fund_ids.get(r["code"])
        if mid and fid and fid not in update_map:
            update_map[fid] = mid

    if not update_map:
        return 0

    from collections import defaultdict

    from sqlalchemy import update

    # 按经理分组，一次 UPDATE 覆盖多只基金，避免逐条提交
    grouped: dict[int, list[int]] = defaultdict(list)
    for fid, mid in update_map.items():
        grouped[mid].append(fid)

    for mid, fund_ids in grouped.items():
        for batch in chunks(fund_ids, 1000):
            await session.execute(update(Fund).where(Fund.id.in_(batch)).values(manager_id=mid))
    await session.commit()

    logger.info("[关联] 回填 %d 只基金的经理（%s）", len(update_map), _elapsed())
    return len(update_map)


async def link_companies(session: AsyncSession) -> int:
    """用基金经理的所属公司回填 funds.company_id。

    基金列表接口本身不带公司字段，而经理接口带"所属公司"，
    且基金经理所属公司与其管理的基金公司基本一致，用它做关联是成本最低的可靠方式。
    """
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE funds f
            JOIN fund_managers m ON f.manager_id = m.id
            SET f.company_id = m.company_id
            WHERE f.company_id IS NULL AND m.company_id IS NOT NULL
            """
        )
    )
    await session.commit()
    affected = result.rowcount or 0
    logger.info("[关联] 回填 %d 只基金的公司（%s）", affected, _elapsed())
    return affected


# ---------------------------------------------------------------- 入口
async def run(mode: str, limit: int | None, codes: list[str] | None) -> None:
    async with async_session_factory() as session:
        if mode in {"quick", "all"}:
            company_ids = await sync_companies(session)
            await sync_funds(session)
            manager_ids = await sync_managers(session, company_ids)
            await link_managers(session, manager_ids)
            await link_companies(session)
            await sync_snapshots(session)
        if mode in {"risk", "all"}:
            await sync_risks(session, limit)
        if mode in {"scale", "all"}:
            await sync_scale(session)
        if mode in {"detail", "all"}:
            await sync_details(session, limit, codes)
        if mode in {"navs", "all"}:
            await sync_navs(session, limit)
        if mode in {"holdings", "all"}:
            await sync_holdings(session, limit, codes)
    await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="基金数据同步")
    parser.add_argument(
        "--mode",
        choices=["quick", "risk", "scale", "detail", "navs", "holdings", "all"],
        default="quick",
        help="quick=基础数据；risk=风险指标；navs=净值序列；holdings=季度重仓股；all=全部",
    )
    parser.add_argument("--limit", type=int, default=None, help="限制处理的基金数量（调试用）")
    parser.add_argument(
        "--codes",
        type=str,
        default=None,
        help="只处理指定基金代码，逗号分隔（如 021180,110022，调试用）",
    )
    args = parser.parse_args()
    codes = [c.strip() for c in args.codes.split(",")] if args.codes else None

    setup_logging()
    logger.info("开始同步，模式=%s limit=%s codes=%s", args.mode, args.limit, codes)
    asyncio.run(run(args.mode, args.limit, codes))
    logger.info("同步结束，耗时 %s", _elapsed())


if __name__ == "__main__":
    main()
