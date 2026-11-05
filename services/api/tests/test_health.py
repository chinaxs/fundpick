"""健康检查接口测试（不依赖数据库）。"""

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.headers.get("X-Request-ID")


async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["api"] == "/api/v1"


async def test_unauthorized(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 40100
