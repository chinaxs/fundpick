"""初始化数据：创建超管账号与示例文章。

用法：
    uv run python -m scripts.seed
"""

import asyncio
from datetime import datetime

from sqlalchemy import select

from app.core.logging import get_logger, setup_logging
from app.core.security import hash_password
from app.db.session import async_session_factory, dispose_engine
from app.models.article import Article, ArticleStatus
from app.models.user import User

logger = get_logger("seed")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123456"


async def seed() -> None:
    async with async_session_factory() as session:
        exists = (
            await session.execute(select(User).where(User.username == ADMIN_USERNAME))
        ).scalar_one_or_none()
        if exists:
            logger.info("管理员账号已存在，跳过")
        else:
            session.add(
                User(
                    username=ADMIN_USERNAME,
                    email="admin@example.com",
                    full_name="超级管理员",
                    hashed_password=hash_password(ADMIN_PASSWORD),
                    is_superuser=True,
                    is_active=True,
                )
            )
            logger.info("已创建管理员：%s / %s", ADMIN_USERNAME, ADMIN_PASSWORD)

        article_exists = (await session.execute(select(Article).limit(1))).scalar_one_or_none()
        if not article_exists:
            session.add(
                Article(
                    title="2026 年公募基金三季度观察：权益回暖，债券承压",
                    slug="market-review-2026q3",
                    summary=(
                        "近一年权益类基金平均收益转正，债券型基金受利率波动影响收益收窄。"
                        "本文从类型分布、收益分位与回撤三个维度梳理当前市场结构。"
                    ),
                    content=(
                        "## 一、整体表现\n\n"
                        "全市场两万余只公募基金中，近一年取得正收益的占比约 45%，"
                        "收益中枢集中在 -10% 至 +10% 区间。\n\n"
                        "## 二、类型分化\n\n"
                        "- **债券型**：平均收益为正，波动与回撤显著低于权益类。\n"
                        "- **混合型**：数量最多，内部差异极大，选基比选类型更重要。\n"
                        "- **指数型**：收益与跟踪标的高度相关，费率优势在长期更明显。\n\n"
                        "> 数据来自公开渠道，仅作方法演示，不构成投资建议。"
                    ),
                    status=ArticleStatus.PUBLISHED,
                    published_at=datetime.now(),
                )
            )
            logger.info("已创建示例文章：welcome")

        await session.commit()
    await dispose_engine()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(seed())
