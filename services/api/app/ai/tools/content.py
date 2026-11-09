"""内容类工具：把已有 service 能力暴露给智能体。

设计约束（见 docs/CONVENTIONS.md 第 6 节）：
1. 工具只调用 service，不直接写 SQL —— 保证软删除、状态过滤、权限规则一致；
2. 默认只读；写操作必须显式标注并加确认；
3. 工具自己管理会话（没有 HTTP 请求上下文），用完即释放。
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.core.exceptions import NotFoundError
from app.db.session import async_session_factory
from app.schemas.common import PageParams
from app.services.article import ArticleService


def _format_list(items: list) -> str:  # type: ignore[type-arg]
    lines = []
    for item in items:
        published = item.published_at.strftime("%Y-%m-%d") if item.published_at else "未发布"
        lines.append(
            f"- 《{item.title}》 slug={item.slug} 发布={published} 浏览={item.view_count}\n"
            f"  摘要：{item.summary or '（无摘要）'}"
        )
    return "\n".join(lines)


@tool
async def search_articles(keyword: str = "", limit: int = 5) -> str:
    """搜索已发布的文章，按标题或摘要模糊匹配。

    Args:
        keyword: 关键词，留空则返回最新文章。
        limit: 返回条数，1-10 之间。
    """
    size = max(1, min(int(limit), 10))
    async with async_session_factory() as session:
        result = await ArticleService(session).list_published(
            PageParams(page=1, page_size=size), keyword or None
        )

    if not result.items:
        return "没有找到匹配的已发布文章。"
    return f"共 {result.total} 篇匹配，展示前 {len(result.items)} 篇：\n" + _format_list(
        list(result.items)
    )


@tool
async def get_article(slug: str) -> str:
    """按 slug 读取一篇已发布文章的正文，用于总结或改写建议。

    Args:
        slug: 文章的 URL 标识，例如 welcome。
    """
    async with async_session_factory() as session:
        try:
            article = await ArticleService(session).get_published_by_slug(slug, count_view=False)
        except NotFoundError:
            return f"未找到 slug={slug} 的已发布文章。"

    body = article.content or "（无正文）"
    return f"标题：{article.title}\n摘要：{article.summary or '（无）'}\n\n{body[:3000]}"


@tool
async def content_overview() -> str:
    """获取站点内容概况：文章总数与已发布数量。用于回答"现在有多少内容"这类问题。"""
    async with async_session_factory() as session:
        stats = await ArticleService(session).stats()
    return f"文章总数 {stats['total']} 篇，其中已发布 {stats['published']} 篇。"


# 智能体可用工具清单：新增工具在此登记
ALL_TOOLS = [search_articles, get_article, content_overview]
