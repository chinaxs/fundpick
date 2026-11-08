"""文章版本：每次保存留快照，恢复追加新版本而不是覆盖历史。"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.session import async_session_factory
from app.models.article import Article
from app.models.article_version import ArticleVersion

BASE = "/api/v1/admin/articles"
PASSWORD = "Admin@123456"


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/admin/auth/login", json={"username": "admin", "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture
async def article(client: AsyncClient, admin_headers: dict) -> dict:
    slug = f"ver-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        BASE,
        json={
            "title": "版本测试 v1",
            "slug": slug,
            "summary": "初版摘要",
            "content": "# 初版\n\n第一版正文。",
            "category": "policy",
            "status": "draft",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    yield body
    async with async_session_factory() as session:
        await session.execute(
            ArticleVersion.__table__.delete().where(ArticleVersion.article_id == body["id"])
        )
        await session.execute(delete(Article).where(Article.id == body["id"]))
        await session.commit()


async def test_create_writes_first_version(
    client: AsyncClient, admin_headers: dict, article: dict
) -> None:
    resp = await client.get(f"{BASE}/{article['id']}/versions", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    versions = resp.json()["data"]
    assert [row["version"] for row in versions] == [1]
    assert versions[0]["title"] == "版本测试 v1"
    assert versions[0]["edited_by"] == "admin"


async def test_update_appends_version_with_new_content(
    client: AsyncClient, admin_headers: dict, article: dict
) -> None:
    updated = await client.patch(
        f"{BASE}/{article['id']}",
        json={"title": "版本测试 v2", "content": "第二版正文。", "category": "market"},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    versions = (await client.get(f"{BASE}/{article['id']}/versions", headers=admin_headers)).json()[
        "data"
    ]
    assert [row["version"] for row in versions] == [2, 1]
    latest = versions[0]
    assert latest["title"] == "版本测试 v2"
    assert latest["content"] == "第二版正文。"
    assert latest["category"] == "market"


async def test_restore_rolls_back_content_and_keeps_history(
    client: AsyncClient, admin_headers: dict, article: dict
) -> None:
    await client.patch(
        f"{BASE}/{article['id']}",
        json={"title": "版本测试 v2", "content": "第二版正文。"},
        headers=admin_headers,
    )

    restored = await client.post(
        f"{BASE}/{article['id']}/versions/1/restore", headers=admin_headers
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["title"] == "版本测试 v1"

    versions = (await client.get(f"{BASE}/{article['id']}/versions", headers=admin_headers)).json()[
        "data"
    ]
    # 恢复本身也是一次保存：追加 v3，v1/v2 都还在
    assert [row["version"] for row in versions] == [3, 2, 1]
    assert versions[0]["content"] == "# 初版\n\n第一版正文。"


async def test_restore_missing_version_returns_404(
    client: AsyncClient, admin_headers: dict, article: dict
) -> None:
    resp = await client.post(f"{BASE}/{article['id']}/versions/99/restore", headers=admin_headers)
    assert resp.status_code == 404


async def test_versions_require_login(client: AsyncClient, article: dict) -> None:
    assert (await client.get(f"{BASE}/{article['id']}/versions")).status_code == 401


async def test_concurrent_updates_produce_distinct_versions(client, admin_headers, article):
    responses = await asyncio.gather(
        *[
            client.patch(
                f"{BASE}/{article['id']}",
                json={"title": f"并发更新 {index}"},
                headers=admin_headers,
            )
            for index in range(2)
        ]
    )
    assert all(response.status_code == 200 for response in responses)
    versions = (await client.get(f"{BASE}/{article['id']}/versions", headers=admin_headers)).json()[
        "data"
    ]
    assert [version["version"] for version in versions] == [3, 2, 1]
    assert {version["title"] for version in versions[:2]} == {"并发更新 0", "并发更新 1"}


async def test_snapshot_failure_does_not_save_article(client, admin_headers, article, monkeypatch):
    from app.core.exceptions import ValidationError
    from app.services.article_version import ArticleVersionService

    async def fail_snapshot(*args):
        raise ValidationError("版本保存失败")

    monkeypatch.setattr(ArticleVersionService, "snapshot", fail_snapshot)
    response = await client.patch(
        f"{BASE}/{article['id']}", json={"title": "不应保存"}, headers=admin_headers
    )
    assert response.status_code == 422
    detail = (await client.get(f"{BASE}/{article['id']}", headers=admin_headers)).json()["data"]
    assert detail["title"] == article["title"]
