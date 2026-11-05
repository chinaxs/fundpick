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
                    title="欢迎使用 portal",
                    slug="welcome",
                    summary="这是一条由初始化脚本生成的示例文章。",
                    content="# 欢迎\n\n你可以登录后台管理文章，门户会同步展示。",
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
