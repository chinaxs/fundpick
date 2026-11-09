"""CORS 回归测试。

浏览器判断跨域用的是「协议 + 主机 + 端口」三元组，因此下面这些在本机
**是五个不同的源**：localhost:3000 / 127.0.0.1:3000 / [::1]:3000 / :5174 ...
历史问题：白名单只枚举了 localhost，用 127.0.0.1 打开门户就整页报 CORS 错误，
而且 curl 不带 Origin 头，测不出来。这里固定住行为，防止再次收窄。
"""

from httpx import AsyncClient

LOCAL_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5174",
    "http://localhost:8080",  # 换端口也应放行（开发环境）
]


async def test_local_origins_allowed(client: AsyncClient) -> None:
    for origin in LOCAL_ORIGINS:
        resp = await client.get("/api/v1/health", headers={"Origin": origin})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin, origin


async def test_foreign_origin_rejected(client: AsyncClient) -> None:
    """外部域名不应被放行，避免正则被写成通配。"""
    resp = await client.get("/api/v1/health", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in resp.headers


async def test_preflight(client: AsyncClient) -> None:
    resp = await client.options(
        "/api/v1/admin/auth/login",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    assert "POST" in (resp.headers.get("access-control-allow-methods") or "")
