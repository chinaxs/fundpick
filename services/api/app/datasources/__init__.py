"""数据源工厂：业务代码只通过这里拿 provider。

当前只有 akshare；换持牌数据源时在这里切换，不改调用方。
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.datasources.akshare_source import AkShareProvider
from app.datasources.base import RANK_CATEGORIES, FundDataProvider

logger = get_logger(__name__)

_provider: FundDataProvider | None = None


def get_provider() -> FundDataProvider:
    global _provider
    if _provider is None:
        _provider = AkShareProvider()
        logger.info("数据源已初始化: %s", _provider.name)
    return _provider


__all__ = ["RANK_CATEGORIES", "FundDataProvider", "get_provider"]
