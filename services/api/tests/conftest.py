"""pytest 全局配置。"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import dispose_engine
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """不启真实端口的 ASGI 客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _reset_engine() -> AsyncIterator[None]:
    """每个用例结束后释放连接池。

    pytest-asyncio 默认按函数作用域建事件循环，而 SQLAlchemy 的连接池是进程级的：
    上一个用例的连接会残留下来，下一个用例复用时就会报
    "got Future attached to a different loop"。显式 dispose 让连接随循环一起回收。
    """
    yield
    await dispose_engine()
