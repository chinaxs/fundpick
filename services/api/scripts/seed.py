"""Create an initial staff administrator; optional, explicitly marked demo content.

Interactive: uv run python -m scripts.seed
Unattended: INITIAL_ADMIN_PASSWORD=... uv run python -m scripts.seed
Existing accounts are never reset, re-enabled, or promoted by this command.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Callable

from sqlalchemy import select

from app.core.logging import get_logger, setup_logging
from app.core.security import hash_password
from app.db.session import async_session_factory, dispose_engine
from app.models.article import Article, ArticleStatus
from app.models.staff import StaffUser

logger = get_logger("seed")


def validate_admin_password(password: str) -> str:
    if not 12 <= len(password.encode("utf-8")) <= 72:
        raise ValueError("管理员密码须为12至72个UTF-8字节")
    if password.casefold() in {"admin@123456", "password123456", "changeme123456"}:
        raise ValueError("请设置自己的管理员密码，不能使用示例密码")
    if (
        sum(
            (
                any(c.islower() for c in password),
                any(c.isupper() for c in password),
                any(c.isdigit() for c in password),
                any(not c.isalnum() for c in password),
            )
        )
        < 3
    ):
        raise ValueError("管理员密码须包含大小写字母、数字、符号中的至少三类")
    return password


def read_admin_password() -> str:
    value = os.getenv("INITIAL_ADMIN_PASSWORD")
    if value:
        return validate_admin_password(value)
    if not sys.stdin.isatty():
        raise ValueError("首次初始化请设置INITIAL_ADMIN_PASSWORD，或在终端交互运行make seed")
    first = getpass.getpass("设置后台管理员密码（至少12字节，不回显）：")
    if first != getpass.getpass("再次输入密码："):
        raise ValueError("两次密码不一致")
    return validate_admin_password(first)


async def seed(
    username: str = "admin",
    *,
    password_provider: Callable[[], str] = read_admin_password,
    demo_content: bool = False,
) -> None:
    username = username.strip()
    if not 3 <= len(username) <= 50:
        raise ValueError("管理员用户名长度须为3至50个字符")
    async with async_session_factory() as session:
        existing = await session.scalar(select(StaffUser).where(StaffUser.username == username))
        if existing is not None:
            if existing.deleted_at or not existing.is_active or not existing.is_superuser:
                raise ValueError("同名账号已存在且不能作为启用的超管使用，请由现有管理员处理")
            logger.info("后台管理员已存在，保留原密码和权限：%s", username)
        else:
            password = validate_admin_password(password_provider())
            session.add(
                StaffUser(
                    username=username,
                    full_name="管理员",
                    hashed_password=hash_password(password),
                    is_superuser=True,
                    is_active=True,
                )
            )
            logger.info("已创建后台管理员：%s（密码不写入日志）", username)

        if demo_content:
            slug = "demo-fund-recording-guide"
            existing_article = await session.scalar(select(Article.id).where(Article.slug == slug))
            if existing_article is None:
                session.add(
                    Article(
                        title="【示例】如何使用基金模拟交易与持仓记录",
                        slug=slug,
                        summary="演示内容：记录外部平台买卖，理解净值日期、待入账与收益统计。",
                        content=(
                            "## 示例说明\n\n这是一篇安装时按需创建的演示草稿，"
                            "不包含真实行情或会员数据。\n\n买入填写金额与下单时间，卖出填写份额；"
                            "系统按对应净值日查询数据。本站不执行真实基金交易，"
                            "自动计算结果与平台实际结果存在差异时，可按平台信息核对。"
                        ),
                        status=ArticleStatus.DRAFT,
                    )
                )
        await session.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=os.getenv("INITIAL_ADMIN_USERNAME", "admin"))
    parser.add_argument("--demo-content", action="store_true", help="额外创建明确标记的示例草稿")
    args = parser.parse_args()
    setup_logging()
    try:
        await seed(args.username, demo_content=args.demo_content)
    except ValueError as error:
        parser.exit(2, f"初始化未完成：{error}\n")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
