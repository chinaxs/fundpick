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

from sqlalchemy import select, text, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, setup_logging
from app.datasources import RANK_CATEGORIES, get_provider
from app.datasources.base import FundSnapshot
from app.db.session import async_session_factory, dispose_engine
from app.fund_search import pinyin_index
from app.fund_sectors import SECTOR_LABELS, detect_sector
from app.job_progress import JobProgress, SyncCancelled, summarize_failures
from app.models import (
    Fund,
    FundCompany,
    FundManager,
    FundMetric,
    FundNav,
    FundType,
    RiskLevel,
)
from app.sync_modes import SYNC_MODES

logger = get_logger("sync_funds")
BATCH = 500
STARTED_AT = time.time()
# 后台触发时才有 job_id；CLI 直接运行时所有进度上报都是空操作
PROGRESS = JobProgress(None)
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
    payload = []
    for b in basics:
        full, initials = pinyin_index(b["name"])
        payload.append(
            {
                "code": b["code"],
                "name": b["name"],
                "type": map_fund_type(b["raw_type"]),
                "full_name": None,
                "name_pinyin": full,
                "name_initials": initials,
            }
        )
    total = await upsert(session, Fund, payload, ["name", "type", "name_pinyin", "name_initials"])
    logger.info("[基金] 基础信息 %d 条（%s）", total, _elapsed())
    return total


def _load_fund_basics() -> list[dict[str, str]]:
    provider = get_provider()
    return [{"code": f.code, "name": f.name, "raw_type": f.raw_type} for f in provider.list_funds()]


async def sync_snapshots(session: AsyncSession, codes: list[str] | None = None) -> int:
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
    if codes:
        selected = set(codes)
        snapshots = [snapshot for snapshot in snapshots if snapshot.code in selected]
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


async def sync_risks(
    session: AsyncSession, limit: int | None, codes: list[str] | None = None
) -> int:
    """风险指标：新增与最新净值基准日不一致的 1y/3y/5y 快照。"""
    stmt = (
        select(Fund.id, Fund.code, Fund.latest_nav_date)
        .outerjoin(
            FundMetric,
            (FundMetric.fund_id == Fund.id) & (FundMetric.period == "1y"),
        )
        .where(
            Fund.deleted_at.is_(None),
            Fund.latest_nav_date.is_not(None),
            FundMetric.risk_nav_date.is_distinct_from(Fund.latest_nav_date),
        )
        .distinct()
        .order_by(Fund.id)
    )
    if codes:
        stmt = stmt.where(Fund.code.in_(codes))
    funds = (await session.execute(stmt)).all()
    if limit:
        funds = funds[:limit]

    provider = get_provider()
    PROGRESS.begin("risk", len(funds))
    done = 0
    for idx, (fund_id, code, nav_date) in enumerate(funds, start=1):
        PROGRESS.checkpoint()
        try:
            rows = await asyncio.to_thread(provider.risk_metrics, code)
        except Exception as exc:
            logger.debug("[风险] %s 失败：%s", code, exc)
            PROGRESS.fail(code, str(exc))
            continue

        by_period = {row.period: row for row in rows}
        payload = []
        for period in ("1y", "3y", "5y"):
            row = by_period.get(period)
            payload.append(
                {
                    "fund_id": fund_id,
                    "period": period,
                    "risk_nav_date": nav_date,
                    "risk_source": (
                        row.source if row and row.source else f"{provider.name} 风险指标"
                    ),
                    "volatility": row.volatility if row else None,
                    "sharpe": row.sharpe if row else None,
                    "max_drawdown": row.max_drawdown if row else None,
                }
            )
        await upsert(
            session,
            FundMetric,
            payload,
            ["risk_nav_date", "risk_source", "volatility", "sharpe", "max_drawdown"],
        )
        done += 1
        PROGRESS.advance(ok=1)

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
            await session.execute(select(Fund.id, Fund.code).where(Fund.code.in_(codes)))
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
    PROGRESS.begin("detail", len(funds))
    updated = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        PROGRESS.checkpoint()
        try:
            profile = await asyncio.to_thread(provider.fund_profile, code)
        except Exception as exc:
            logger.debug("[档案] %s 失败：%s", code, exc)
            PROGRESS.fail(code, str(exc))
            continue
        if profile is None:
            PROGRESS.advance(skipped=1)
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
        PROGRESS.advance(ok=1)
        if idx % 50 == 0:
            await session.commit()
            logger.info("[档案] %d/%d 已处理（%s）", idx, len(funds), _elapsed())
        await asyncio.sleep(0.05)

    await session.commit()
    logger.info("[档案] 更新 %d 只（%s）", updated, _elapsed())
    return updated


async def sync_navs(
    session: AsyncSession, limit: int | None, codes: list[str] | None = None
) -> int:
    """净值序列：只拉取已有指标、按浏览次数排序的前 N 只，避免全量拉爆。

    全市场 1 万只 × 数千条 ≈ 千万级行，全量拉取需要数小时；
    详情页需要曲线时再按需补齐更划算。
    """
    stmt = select(Fund.id, Fund.code).where(Fund.deleted_at.is_(None)).order_by(Fund.id)
    if codes:
        stmt = stmt.where(Fund.code.in_(codes))
    if limit:
        stmt = stmt.limit(limit)
    funds = (await session.execute(stmt)).all()

    provider = get_provider()
    PROGRESS.begin("navs", len(funds))
    total = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        PROGRESS.checkpoint()
        try:
            points = await asyncio.to_thread(provider.nav_history, code)
        except Exception as exc:
            logger.debug("[净值] %s 失败：%s", code, exc)
            PROGRESS.fail(code, str(exc))
            continue
        if not points:
            PROGRESS.advance(skipped=1)
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
        PROGRESS.advance(ok=1)
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
    PROGRESS.begin("holdings", len(funds))
    total = 0
    for idx, (fund_id, code) in enumerate(funds, start=1):
        PROGRESS.checkpoint()
        try:
            holdings = await asyncio.to_thread(provider.fund_holdings, code, year)
        except Exception as exc:
            logger.debug("[持仓] %s 失败：%s", code, exc)
            PROGRESS.fail(code, str(exc))
            continue
        if not holdings:
            PROGRESS.advance(skipped=1)
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
        PROGRESS.advance(ok=1)
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


# ---------------------------------------------------------------- 风险等级推导
# 销售机构的产品风险定级没有公开接口，行业通行做法是按基金类型推导
# （与天天基金/蚂蚁财富等平台的展示口径一致）：
#   货币→低；债券→中低；混合 FoF→中；偏股混合/指数→中高；股票/QDII→高。
# 这是"规则推导"而非官方定级，仅填充 NULL，有真实数据时永不覆盖。
TYPE_RISK_MAP: dict[FundType, RiskLevel | None] = {
    FundType.MONEY: RiskLevel.LOW,
    FundType.BOND: RiskLevel.MID_LOW,
    FundType.FOF: RiskLevel.MID,
    FundType.HYBRID: RiskLevel.MID_HIGH,
    FundType.INDEX: RiskLevel.MID_HIGH,
    FundType.STOCK: RiskLevel.HIGH,
    FundType.QDII: RiskLevel.HIGH,
    FundType.OTHER: None,  # 无法判断，保持 NULL
}


async def derive_risk_levels(session: AsyncSession) -> int:
    """按基金类型推导风险等级，只填充 NULL 行。"""
    affected = 0
    for fund_type, risk in TYPE_RISK_MAP.items():
        if risk is None:
            continue
        result = await session.execute(
            text(
                "UPDATE funds SET risk_level = :risk "
                "WHERE type = :type AND risk_level IS NULL AND deleted_at IS NULL"
            ),
            {"risk": risk.value, "type": fund_type.value},
        )
        affected += result.rowcount or 0
        logger.info(
            "[风险等级] %s -> %s，更新 %d 行",
            fund_type.value,
            risk.value,
            result.rowcount or 0,
        )
    await session.commit()
    remaining = (
        await session.execute(
            text("SELECT count(*) FROM funds WHERE risk_level IS NULL AND deleted_at IS NULL")
        )
    ).scalar()
    logger.info("[风险等级] 共填充 %d 行，剩余未定级 %d 行（%s）", affected, remaining, _elapsed())
    return affected


# ---------------------------------------------------------------- 主题板块推导
async def derive_sectors(session: AsyncSession, force: bool = False) -> int:
    """按名称/跟踪指数推导主题板块（规则见 app.fund_sectors）。

    默认只填 NULL；--force 时按当前规则全量重算（规则调整后用）。
    无主题词的基金保持 NULL，前端显示"综合"，不强行归类。
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, name, full_name, tracking_index, sector FROM funds "
                "WHERE deleted_at IS NULL"
            )
        )
    ).all()

    buckets: dict[str, list[int]] = {}
    clear_ids: list[int] = []
    for fund_id, name, full_name, tracking_index, current in rows:
        if current is not None and not force:
            continue
        target = detect_sector(name, full_name, tracking_index)
        if target == current:
            continue
        if target is None:
            clear_ids.append(fund_id)
        else:
            buckets.setdefault(target, []).append(fund_id)

    affected = 0
    for sector, ids in buckets.items():
        for i in range(0, len(ids), BATCH):
            result = await session.execute(
                update(Fund).where(Fund.id.in_(ids[i : i + BATCH])).values(sector=sector)
            )
            affected += result.rowcount or 0
        logger.info("[板块] %s -> %d 只", SECTOR_LABELS.get(sector, sector), len(ids))
    for i in range(0, len(clear_ids), BATCH):
        result = await session.execute(
            update(Fund).where(Fund.id.in_(clear_ids[i : i + BATCH])).values(sector=None)
        )
        affected += result.rowcount or 0

    await session.commit()
    logger.info("[板块] 共更新 %d 行，规则覆盖 %d 个板块（%s）", affected, len(buckets), _elapsed())
    return affected


# ---------------------------------------------------------------- 入口
async def backfill_pinyin(session: AsyncSession, force: bool = False) -> int:
    """回填搜索用的拼音列。

    只处理 name_pinyin 为空的行（--force 时全量重算），
    这样日常加新基金时跑一次也是"补差量"，不会把 28k 行全部重写。
    """
    stmt = select(Fund.id, Fund.name, Fund.name_pinyin)
    if not force:
        stmt = stmt.where(Fund.name_pinyin.is_(None))
    rows = (await session.execute(stmt)).all()

    total = 0
    for start in range(0, len(rows), 500):
        chunk = rows[start : start + 500]
        payload = []
        for fund_id, name, _ in chunk:
            full, initials = pinyin_index(name or "")
            payload.append({"id": fund_id, "name_pinyin": full, "name_initials": initials})
        await session.execute(update(Fund), payload)
        total += len(payload)
        logger.info("[拼音] 已回填 %d / %d", total, len(rows))

    await session.commit()
    logger.info("[拼音] 完成，共 %d 条（%s）", total, _elapsed())
    return total


async def run(mode: str, limit: int | None, codes: list[str] | None, force: bool = False) -> None:
    async def step(name: str, factory: Any, *, self_report: bool = False) -> Any:
        """跑一个阶段并上报进度。

        `self_report=True` 表示该函数自己逐条上报（见 sync_risks / sync_navs），
        这里就不再按返回值累加，避免同一批条目被计两次。
        """
        PROGRESS.begin(name)
        PROGRESS.checkpoint()
        outcome = await factory()
        if not self_report:
            PROGRESS.advance(ok=outcome if isinstance(outcome, int) else 1)
        return outcome

    async with async_session_factory() as session:
        if mode in {"quick", "all"}:
            company_ids = await step("company", lambda: sync_companies(session))
            await step("fund", lambda: sync_funds(session))
            manager_ids = await step("manager", lambda: sync_managers(session, company_ids))
            await step("manager-link", lambda: link_managers(session, manager_ids))
            await step("company-link", lambda: link_companies(session))
            await step("snapshot", lambda: sync_snapshots(session))
        if mode == "snapshot":
            await step("snapshot", lambda: sync_snapshots(session, codes))
        if mode in {"risk", "all"}:
            await step("risk", lambda: sync_risks(session, limit, codes), self_report=True)
        if mode == "risk-level":
            await step("risk-level", lambda: derive_risk_levels(session))
        if mode == "sector":
            await step("sector", lambda: derive_sectors(session, force=force))
        if mode in {"pinyin", "all"}:
            await step("pinyin", lambda: backfill_pinyin(session, force=force))
        if mode in {"scale", "all"}:
            await step("scale", lambda: sync_scale(session))
        if mode in {"detail", "all"}:
            await step("detail", lambda: sync_details(session, limit, codes), self_report=True)
        if mode in {"navs", "all"}:
            await step("navs", lambda: sync_navs(session, limit, codes), self_report=True)
        if mode in {"holdings", "all"}:
            await step("holdings", lambda: sync_holdings(session, limit, codes), self_report=True)
    if mode in {"quick", "snapshot", "navs", "all"}:
        from app.services.automatic_trade import reconcile_after_sync

        await step("reconcile", reconcile_after_sync)
    PROGRESS.begin("done")
    await dispose_engine()


def _write_job_result(job_id: int | None, status: str, started: float, message: str) -> None:
    """后台触发模式下写结果文件，供 API 回填 sync_jobs 状态。

    刻意不直接写数据库：采集脚本保持纯 CLI，且 API 进程重启后
    仍能从文件恢复任务结果，不会出现永远 running 的僵尸任务。
    计数一并写入，避免进程结束后进度文件被清理导致统计丢失。
    """
    if job_id is None:
        return
    import json
    from pathlib import Path

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_ms": int((time.time() - started) * 1000),
        "message": message[:500],
        "counts": {
            "phase": PROGRESS.phase,
            "total": PROGRESS.total,
            "succeeded": PROGRESS.succeeded,
            "failed": PROGRESS.failed,
            "skipped": PROGRESS.skipped,
            "failures": PROGRESS.failures,
        },
    }
    try:
        (log_dir / f"sync_job_{job_id}.result.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:  # pragma: no cover - 磁盘异常不应影响采集结果
        logger.warning("[任务] 写入结果文件失败: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="基金数据同步")
    parser.add_argument(
        "--mode",
        choices=SYNC_MODES,
        default="quick",
        help=(
            "quick=基础数据；risk=风险指标；risk-level=按类型推导风险等级；"
            "sector=按名称推导主题板块；navs=净值序列；holdings=季度重仓股；all=全部"
        ),
    )
    parser.add_argument("--limit", type=int, default=None, help="限制处理的基金数量（调试用）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="sector 模式下按当前规则全量重算（默认只填 NULL）",
    )
    parser.add_argument(
        "--codes",
        type=str,
        default=None,
        help="只处理指定基金代码，逗号分隔（如 021180,110022，调试用）",
    )
    parser.add_argument(
        "--job-id",
        type=int,
        default=None,
        help="后台触发时传入的任务 ID，用于写结果文件（CLI 手动执行时无需传）",
    )
    args = parser.parse_args()
    codes = [c.strip() for c in args.codes.split(",")] if args.codes else None

    global PROGRESS
    PROGRESS = JobProgress(args.job_id)

    setup_logging()
    logger.info(
        "开始同步，模式=%s limit=%s codes=%s force=%s job=%s",
        args.mode,
        args.limit,
        codes,
        args.force,
        args.job_id,
    )
    try:
        asyncio.run(run(args.mode, args.limit, codes, args.force))
    except SyncCancelled:
        logger.info("收到取消请求，本轮采集已停止（%s）", _elapsed())
        _write_job_result(args.job_id, "cancelled", STARTED_AT, "已按请求取消")
        return
    except Exception as exc:
        logger.exception("同步失败: %s", exc)
        _write_job_result(args.job_id, "failed", STARTED_AT, str(exc))
        raise SystemExit(1) from exc
    logger.info("同步结束，耗时 %s", _elapsed())
    status = "partial_success" if PROGRESS.failed else "success"
    message = summarize_failures(PROGRESS.failures) or "同步完成"
    _write_job_result(args.job_id, status, STARTED_AT, message)


if __name__ == "__main__":
    main()
