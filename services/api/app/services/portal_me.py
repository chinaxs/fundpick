"""会员自助服务：个人中心设置 + 工作台统计。

设计取舍：工作台统计在 Python 侧完成。会员关注数通常几十只，
一次 join 取回后在内存里分组，比 6 条 GROUP BY SQL 更易读、更易测；
真出现"关注上千只"的账号时，list_for_dashboard 的 limit 会兜住上限。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.core.security import verify_password
from app.fund_sectors import SECTOR_LABELS
from app.models.fund_favorite import FundFavorite
from app.models.fund_position import FundPosition
from app.models.user import User
from app.repositories.favorite import FavoriteRepository
from app.repositories.user import UserRepository
from app.schemas.portal_me import (
    DashboardDistributionItem,
    DashboardFundItem,
    DashboardResponse,
    DashboardSummary,
    ProfileUpdateRequest,
)
from app.services.auth import AuthService
from app.services.fund import RISK_LABELS, TYPE_LABELS
from app.services.portal_position import PositionService

# 收益分桶（与全市场分布保持一致口径）
RETURN_BUCKETS: list[tuple[str, float | None, float | None]] = [
    (">20%", 20, None),
    ("10~20%", 10, 20),
    ("0~10%", 0, 10),
    ("-10~0%", -10, 0),
    ("-20~-10%", -20, -10),
    ("<-20%", None, -20),
]


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _return_of(metric: Any) -> float | None:
    value = getattr(metric, "return_rate", None)
    return float(value) if value is not None else None


def _bucket_of(value: float) -> str:
    for label, low, high in RETURN_BUCKETS:
        if (low is None or value >= low) and (high is None or value < high):
            return label
    return RETURN_BUCKETS[-1][0]


class PortalMeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.favorites = FavoriteRepository(session)
        self.auth = AuthService(session)

    # ---------------------------------------------------------- 个人中心
    async def update_profile(self, user: User, payload: ProfileUpdateRequest) -> User:
        """只改展示类字段；邮箱唯一性校验排除自己。"""
        data = payload.model_dump(exclude_unset=True)

        if "email" in data:
            email = data["email"] or None
            if email:
                existing = await self.users.get_by(email=email)
                if existing and existing.id != user.id:
                    raise ConflictError("邮箱已被占用")
            data["email"] = email

        for key in ("full_name", "avatar_url"):
            if key in data:
                data[key] = data[key] or None

        await self.users.update(user, **data)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if len(new_password) < 8:
            raise ValidationError("新密码至少 8 位")
        await self.auth.change_password(user, old_password, new_password)

    async def deactivate(self, user: User, password: str) -> None:
        """注销账号：校验密码 → 清理关注 → 软删用户。

        软删后 CurrentUser 查不到记录，现有 token 立即失效。
        """
        if not verify_password(password, user.hashed_password):
            raise UnauthorizedError("密码不正确")
        await self.session.execute(
            sql_delete(FundFavorite).where(FundFavorite.user_id == user.id)
        )
        await self.session.execute(
            sql_delete(FundPosition).where(FundPosition.user_id == user.id)
        )
        await self.users.delete(user, soft=True)
        await self.session.commit()

    # ---------------------------------------------------------- 工作台
    async def dashboard(self, user_id: int, period: str = "1y") -> DashboardResponse:
        rows = await self.favorites.list_for_dashboard(user_id, period)
        total = len(rows)

        returns: list[float] = []
        sharpes: list[float] = []
        nav_dates: list[str] = []
        by_type: dict[str, list[float | None]] = defaultdict(list)
        by_risk: dict[str, int] = defaultdict(int)
        by_sector: dict[str, int] = defaultdict(int)
        by_bucket: dict[str, int] = defaultdict(int)
        added_recently = 0
        cutoff = datetime.now() - timedelta(days=7)

        items: list[DashboardFundItem] = []
        for fav, fund, metric in rows:
            ret = _return_of(metric)
            if ret is not None:
                returns.append(ret)
                by_bucket[_bucket_of(ret)] += 1
            by_type[str(fund.type)].append(ret)
            if fund.risk_level:
                by_risk[str(fund.risk_level)] += 1
            if fund.sector:
                by_sector[str(fund.sector)] += 1
            if fund.latest_nav_date:
                nav_dates.append(str(fund.latest_nav_date))
            sharpe = getattr(metric, "sharpe", None)
            if sharpe is not None:
                sharpes.append(float(sharpe))
            if fav.created_at and fav.created_at >= cutoff:
                added_recently += 1

            items.append(
                DashboardFundItem(
                    code=fund.code,
                    name=fund.name,
                    type=str(fund.type),
                    sector=fund.sector,
                    risk_level=fund.risk_level,
                    return_rate=ret,
                    max_drawdown=(
                        float(metric.max_drawdown)
                        if metric and metric.max_drawdown is not None
                        else None
                    ),
                    sharpe=float(sharpe) if sharpe is not None else None,
                    latest_nav=float(fund.latest_nav) if fund.latest_nav is not None else None,
                    favored_at=fav.created_at,
                )
            )

        positive = sum(1 for r in returns if r > 0)
        summary = DashboardSummary(
            total_funds=total,
            avg_return=_avg(returns),
            positive_ratio=round(positive / len(returns) * 100, 1) if returns else None,
            avg_sharpe=_avg(sharpes),
            best_return=round(max(returns), 2) if returns else None,
            added_last_7_days=added_recently,
            metric_coverage=round(len(returns) / total * 100, 1) if total else 0,
            latest_nav_date=max(nav_dates) if nav_dates else None,
        )

        type_distribution = [
            DashboardDistributionItem(
                key=key,
                label=TYPE_LABELS.get(key, key),
                count=len(values),
                avg_return=_avg([v for v in values if v is not None]),
            )
            for key, values in by_type.items()
        ]
        type_distribution.sort(key=lambda x: -x.count)

        risk_order = ["low", "mid_low", "mid", "mid_high", "high"]
        risk_distribution = [
            DashboardDistributionItem(
                key=key, label=RISK_LABELS.get(key, key), count=by_risk[key]
            )
            for key in risk_order
            if by_risk.get(key)
        ]
        sector_distribution = [
            DashboardDistributionItem(
                key=key, label=SECTOR_LABELS.get(key, key), count=count
            )
            for key, count in sorted(by_sector.items(), key=lambda x: -x[1])[:8]
        ]
        return_buckets = [
            DashboardDistributionItem(key=label, label=label, count=by_bucket.get(label, 0))
            for label, _low, _high in RETURN_BUCKETS
        ]

        by_return = sorted(
            items,
            key=lambda x: x.return_rate if x.return_rate is not None else float("-inf"),
            reverse=True,
        )
        # 收藏列表给全量（最多 500，与 list_for_dashboard 的 limit 一致）
        position_items, position_summary = await PositionService(self.session).overview(user_id)
        return DashboardResponse(
            period=period,
            summary=summary,
            type_distribution=type_distribution,
            risk_distribution=risk_distribution,
            sector_distribution=sector_distribution,
            return_buckets=return_buckets,
            top_funds=by_return[:5],
            recent_funds=items[:5],  # rows 已按关注时间倒序
            favorites=items,
            positions=position_items,
            position_summary=position_summary,
        )
