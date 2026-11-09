"""Seed deterministic integration-test data into an isolated test database only."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import async_session_factory, dispose_engine
from app.fund_search import pinyin_index
from app.models.fund import Fund, FundType
from app.models.fund_company import FundCompany
from app.models.fund_holding import FundHolding
from app.models.fund_metric import FundMetric
from app.models.fund_nav import FundNav
from app.models.staff import StaffUser

ADMIN_PASSWORD = "Admin@123456"
GENERATED_CODES = range(990_000, 991_200)


async def seed_test_data() -> None:
    if settings.APP_ENV != "test" or "test" not in settings.MYSQL_DB.casefold():
        raise RuntimeError("seed_test_data requires APP_ENV=test and an isolated test database")

    async with async_session_factory() as session:
        staff = (
            await session.execute(
                select(StaffUser).where(
                    StaffUser.username == "admin", StaffUser.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if staff is None:
            session.add(
                StaffUser(
                    username="admin",
                    hashed_password=hash_password(ADMIN_PASSWORD),
                    is_active=True,
                    is_superuser=True,
                )
            )
        else:
            staff.is_active = True
            staff.is_superuser = True
            staff.hashed_password = hash_password(ADMIN_PASSWORD)

        company = (
            await session.execute(
                select(FundCompany).where(FundCompany.name == "易方达基金管理有限公司")
            )
        ).scalar_one_or_none()
        if company is None:
            company = FundCompany(name="易方达基金管理有限公司", short_name="易方达基金")
            session.add(company)
            await session.flush()

        today = date.today()
        latest_date = today - timedelta(days=1)
        specs: list[tuple[str, str, FundType, int | None, str | None]] = [
            ("000001", "华夏成长混合", FundType.HYBRID, None, None),
            ("000003", "中海可转债债券A", FundType.BOND, company.id, None),
            ("000004", "中海可转债债券C", FundType.BOND, company.id, None),
            ("002910", "易方达供需平衡混合", FundType.HYBRID, company.id, None),
            ("021180", "易方达研究精选混合", FundType.HYBRID, company.id, None),
            ("991200", "华夏稳健债券测试基金", FundType.BOND, company.id, None),
        ]
        for index, number in enumerate(GENERATED_CODES):
            sector = "semiconductor" if index < 70 else "new_energy" if index < 140 else None
            specs.append(
                (
                    f"{number:06d}",
                    f"华夏成长混合测试基金{index:04d}",
                    FundType.HYBRID,
                    company.id,
                    sector,
                )
            )

        codes = [spec[0] for spec in specs]
        existing_codes = set(
            (await session.execute(select(Fund.code).where(Fund.code.in_(codes)))).scalars()
        )
        funds = []
        for code, name, fund_type, company_id, sector in specs:
            if code in existing_codes:
                continue
            pinyin, initials = pinyin_index(name)
            funds.append(
                Fund(
                    code=code,
                    name=name,
                    full_name=f"{name}证券投资基金",
                    name_pinyin=pinyin,
                    name_initials=initials,
                    type=fund_type,
                    company_id=company_id,
                    sector=sector,
                    inception_date=date(2015, 1, 1),
                    scale=Decimal("100"),
                    latest_nav=Decimal("1.2500"),
                    latest_nav_date=latest_date,
                    management_fee=Decimal("1.2") if code == "021180" else None,
                    custody_fee=Decimal("0.2") if code == "021180" else None,
                )
            )
        session.add_all(funds)
        await session.flush()

        seeded_funds = (
            await session.execute(select(Fund.id, Fund.code).where(Fund.code.in_(codes)))
        ).all()
        fund_ids = {code: fund_id for fund_id, code in seeded_funds}
        existing_metrics = set(
            (
                await session.execute(
                    select(FundMetric.fund_id, FundMetric.period).where(
                        FundMetric.fund_id.in_(fund_ids.values()), FundMetric.period == "1y"
                    )
                )
            ).all()
        )
        session.add_all(
            [
                FundMetric(
                    fund_id=fund_id,
                    period="1y",
                    nav_date=latest_date,
                    return_rate=Decimal("5.0"),
                    max_drawdown=Decimal("12.0"),
                    volatility=Decimal("15.0"),
                    sharpe=Decimal("0.8"),
                )
                for code, fund_id in fund_ids.items()
                if (fund_id, "1y") not in existing_metrics
            ]
        )

        historical_dates = [today - timedelta(days=130), today - timedelta(days=30), latest_date]
        existing_nav_dates = set(
            (
                await session.execute(
                    select(FundNav.nav_date).where(
                        FundNav.fund_id == fund_ids["021180"],
                        FundNav.nav_date.in_(historical_dates),
                    )
                )
            ).scalars()
        )
        for index, nav_date in enumerate(historical_dates):
            if nav_date not in existing_nav_dates:
                session.add(
                    FundNav(
                        fund_id=fund_ids["021180"],
                        nav_date=nav_date,
                        unit_nav=Decimal("1.10") + Decimal(index) / 10,
                        daily_return=Decimal("0.2"),
                    )
                )

        has_holdings = await session.scalar(
            select(FundHolding.id).where(
                FundHolding.fund_id == fund_ids["021180"], FundHolding.quarter == "2026Q2"
            )
        )
        if has_holdings is None:
            session.add_all(
                [
                    FundHolding(
                        fund_id=fund_ids["021180"],
                        quarter="2026Q2",
                        stock_code="600000",
                        stock_name="浦发银行",
                        rank=1,
                        ratio=Decimal("8.5"),
                    ),
                    FundHolding(
                        fund_id=fund_ids["021180"],
                        quarter="2026Q2",
                        stock_code="000002",
                        stock_name="万科A",
                        rank=2,
                        ratio=Decimal("4.5"),
                    ),
                ]
            )
        await session.commit()

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(seed_test_data())
