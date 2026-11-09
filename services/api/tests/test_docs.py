"""接口文档拆分测试。

两个消费方各看一份文档，避免在长列表里翻找并误调受限接口：

- `/docs/portal` ← `/openapi/portal.json`（只含 `/api/v1/portal/**`）
- `/docs/admin`  ← `/openapi/admin.json`（只含 `/api/v1/admin/**`）
- `/docs`        ← `/openapi.json`（全量，排查跨端问题时用）
"""

from httpx import AsyncClient

PORTAL_PREFIX = "/api/v1/portal"
ADMIN_PREFIX = "/api/v1/admin"


async def test_portal_schema_contains_only_portal_paths(client: AsyncClient) -> None:
    resp = await client.get("/openapi/portal.json")
    assert resp.status_code == 200
    paths = list(resp.json()["paths"])
    assert paths, "门户文档不应为空"
    assert all(p.startswith(PORTAL_PREFIX) for p in paths)


async def test_admin_schema_contains_only_admin_paths(client: AsyncClient) -> None:
    resp = await client.get("/openapi/admin.json")
    assert resp.status_code == 200
    paths = list(resp.json()["paths"])
    assert paths, "后台文档不应为空"
    assert all(p.startswith(ADMIN_PREFIX) for p in paths)


async def test_schemas_do_not_overlap(client: AsyncClient) -> None:
    portal = set((await client.get("/openapi/portal.json")).json()["paths"])
    admin = set((await client.get("/openapi/admin.json")).json()["paths"])
    assert not portal & admin, "同一个接口不应同时出现在两份文档里"


async def test_unused_tags_are_stripped(client: AsyncClient) -> None:
    """切分后只剩被引用的分组，否则 Swagger 侧栏会出现空分组。"""
    portal = (await client.get("/openapi/portal.json")).json()
    tags = [t["name"] for t in portal.get("tags", [])]
    assert tags
    assert all(t.startswith("门户") for t in tags)

    admin = (await client.get("/openapi/admin.json")).json()
    tags = [t["name"] for t in admin.get("tags", [])]
    assert tags
    assert all(t.startswith("后台") for t in tags)


async def test_docs_pages_point_to_their_own_schema(client: AsyncClient) -> None:
    for key, title in (("portal", "Study 门户 API"), ("admin", "Study 后台 API")):
        resp = await client.get(f"/docs/{key}")
        assert resp.status_code == 200
        assert title in resp.text
        assert f"/openapi/{key}.json" in resp.text


async def test_full_schema_still_available(client: AsyncClient) -> None:
    """全量文档保留：切分是视图分层，不是拆服务。"""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert len(paths) > 20
    assert any(p.startswith(PORTAL_PREFIX) for p in paths)
    assert any(p.startswith(ADMIN_PREFIX) for p in paths)
