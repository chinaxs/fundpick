"""pytest 全局配置。"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.session import dispose_engine
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """不启真实端口的 ASGI 客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
def _require_test_database() -> None:
    """Refuse to run destructive integration tests against a non-test database."""
    if settings.APP_ENV != "test" or "test" not in settings.MYSQL_DB.casefold():
        pytest.exit(
            "pytest requires APP_ENV=test and a dedicated MYSQL_DB containing 'test'", returncode=2
        )


@pytest.fixture(autouse=True)
def _isolated_sync_files(monkeypatch, tmp_path, request):
    """Do not read production progress/results or leave test control files in app logs."""
    from pathlib import Path

    from app import job_progress
    from app.services import sync_job

    folder = tmp_path / "sync-control"
    monkeypatch.setattr(job_progress, "LOG_DIR", folder)
    monkeypatch.setattr(sync_job, "LOG_DIR", folder)
    if isinstance(getattr(request.module, "LOG_DIR", None), Path):
        monkeypatch.setattr(request.module, "LOG_DIR", folder)


@pytest.fixture(autouse=True)
async def _reset_engine() -> AsyncIterator[None]:
    """每个用例结束后释放连接池。

    pytest-asyncio 默认按函数作用域建事件循环，而 SQLAlchemy 的连接池是进程级的：
    上一个用例的连接会残留下来，下一个用例复用时就会报
    "got Future attached to a different loop"。显式 dispose 让连接随循环一起回收。
    """
    yield
    await dispose_engine()
