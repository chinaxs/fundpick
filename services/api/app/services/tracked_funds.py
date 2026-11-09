"""Determine funds used by active members, excluding soft-deleted ledger rows."""

from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Fund,
    FundFavorite,
    FundPortfolioFlow,
    FundPosition,
    FundTransaction,
    TradeApplication,
    User,
)


async def tracked_codes(session: AsyncSession, limit: int | None = None) -> list[str]:
    members = select(User.id).where(User.deleted_at.is_(None), User.is_active.is_(True))
    ids = union(
        select(FundFavorite.fund_id).where(FundFavorite.user_id.in_(members)),
        select(FundPosition.fund_id).where(
            FundPosition.user_id.in_(members), FundPosition.deleted_at.is_(None)
        ),
        select(FundTransaction.fund_id).where(
            FundTransaction.user_id.in_(members),
            FundTransaction.status == "confirmed",
            FundTransaction.deleted_at.is_(None),
        ),
        select(FundPortfolioFlow.fund_id).where(
            FundPortfolioFlow.user_id.in_(members), FundPortfolioFlow.deleted_at.is_(None)
        ),
        select(TradeApplication.fund_id).where(
            TradeApplication.user_id.in_(members),
            TradeApplication.status == "pending",
            TradeApplication.deleted_at.is_(None),
        ),
    ).subquery()
    query = (
        select(Fund.code)
        .where(Fund.deleted_at.is_(None), Fund.id.in_(select(ids.c.fund_id)))
        .order_by(Fund.code)
    )
    if limit:
        query = query.limit(limit)
    return list((await session.scalars(query)).all())
