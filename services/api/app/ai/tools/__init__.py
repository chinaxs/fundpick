"""AI 工具统一出口。"""

from app.ai.tools.content import ALL_TOOLS as CONTENT_TOOLS
from app.ai.tools.content import content_overview, get_article, search_articles
from app.ai.tools.portfolio import portfolio_evidence

# 内容助手默认工具集；持仓工具不默认挂载——它需要明确的会员身份，
# 只能由已鉴权的入口按需加入，避免模型越权读取他人账本。
ALL_TOOLS = [*CONTENT_TOOLS]

__all__ = [
    "ALL_TOOLS",
    "CONTENT_TOOLS",
    "content_overview",
    "get_article",
    "portfolio_evidence",
    "search_articles",
]
