"""后台手动同步：权限、并发控制、任务查询与结果恢复。

子进程通过 monkeypatch 掉 SyncJobService.spawn，避免测试真的跑一轮采集。
"""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.session import async_session_factory
from app.models.sync_job import SyncJob
from app.services.sync_job import LOG_DIR, SyncJobService

PASSWORD = "Admin@123456"
STAFF_PASSWORD = "Staff@12345"
BASE = "/api/v1/admin/funds"


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/admin/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, "admin", PASSWORD)


@pytest.fixture
def no_spawn(monkeypatch: pytest.MonkeyPatch):
    """替换子进程启动：只保留任务记录，便于断言状态。"""

    async def fake_spawn(self, job, payload):
        # 用当前进程 PID 模拟"子进程还在跑"，避免僵尸检测把任务判成失败
        job.pid = os.getpid()
        await self.session.commit()

    monkeypatch.setattr(SyncJobService, "spawn", fake_spawn)


@pytest.fixture(autouse=True)
async def cleanup_jobs():
    yield
    async with async_session_factory() as session:
        # 只清理本测试 mock 出来的记录，不碰真实任务历史
        await session.execute(
            delete(SyncJob).where(SyncJob.triggered_by == "admin", SyncJob.pid == os.getpid())
        )
        await session.commit()
    for path in LOG_DIR.glob("sync_job_test_*.result.json"):
        path.unlink(missing_ok=True)


async def test_trigger_requires_superuser(client: AsyncClient, no_spawn: None) -> None:
    """匿名 401；普通员工 403；超管才能触发。"""
    assert (await client.post(f"{BASE}/sync", json={"mode": "quick"})).status_code == 401

    name = f"ts_{uuid4().hex[:8]}"
    admin = await _login(client, "admin", PASSWORD)
    created = await client.post(
        "/api/v1/admin/staff",
        json={"username": name, "password": STAFF_PASSWORD},
        headers=admin,
    )
    assert created.status_code in (200, 201), created.text
    staff_id = created.json()["data"]["id"]
    staff = await _login(client, name, STAFF_PASSWORD)
    forbidden = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=staff)
    assert forbidden.status_code == 403

    ok = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin)
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "running"
    assert ok.json()["data"]["triggered_by"] == "admin"

    async with async_session_factory() as session:
        # 只清理本测试 mock 出来的记录，不碰真实任务历史
        await session.execute(
            delete(SyncJob).where(SyncJob.triggered_by == "admin", SyncJob.pid == os.getpid())
        )
        await session.commit()
    await client.delete(f"/api/v1/admin/staff/{staff_id}", headers=admin)


async def test_duplicate_trigger_rejected(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    first = await client.post(f"{BASE}/sync", json={"mode": "sector"}, headers=admin_headers)
    assert first.status_code == 200, first.text
    job_id = first.json()["data"]["id"]

    second = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
    assert second.status_code == 409, second.text
    assert f"#{job_id}" in second.json()["message"]

    jobs = await client.get(f"{BASE}/sync/jobs", headers=admin_headers)
    assert any(j["id"] == job_id for j in jobs.json()["data"])


async def test_concurrent_triggers_are_serialized_by_database_lock(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    responses = await asyncio.gather(
        *[
            client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
            for _ in range(2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409]


async def test_spawn_failure_is_persisted_as_failed(
    client: AsyncClient, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fail_spawn(self, job, payload):
        raise OSError("spawn unavailable")

    monkeypatch.setattr(SyncJobService, "spawn", fail_spawn)
    response = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
    assert response.status_code == 200, response.text
    job = response.json()["data"]
    assert job["status"] == "failed"
    assert "spawn unavailable" in job["message"]

    async with async_session_factory() as session:
        await session.execute(delete(SyncJob).where(SyncJob.id == job["id"]))
        await session.commit()


async def test_invalid_mode_rejected(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    resp = await client.post(f"{BASE}/sync", json={"mode": "rm -rf"}, headers=admin_headers)
    assert resp.status_code in (400, 422), resp.text


async def test_job_list_and_detail(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(
        f"{BASE}/sync", json={"mode": "risk", "limit": 10}, headers=admin_headers
    )
    job_id = created.json()["data"]["id"]
    assert json.loads(created.json()["data"]["params"]) == {"limit": 10}

    listing = await client.get(f"{BASE}/sync/jobs?limit=5", headers=admin_headers)
    assert listing.status_code == 200
    assert job_id in [j["id"] for j in listing.json()["data"]]

    detail = await client.get(f"{BASE}/sync/jobs/{job_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["mode"] == "risk"

    missing = await client.get(f"{BASE}/sync/jobs/99999999", headers=admin_headers)
    assert missing.status_code == 404


async def test_status_recovered_from_result_file(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    """API 重启后靠脚本写的结果文件恢复状态，不会永远卡在 running。"""
    created = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
    job_id = created.json()["data"]["id"]

    result_path = LOG_DIR / f"sync_job_{job_id}.result.json"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "finished_at": "2026-11-06T22:00:00",
                "duration_ms": 71234,
                "message": "同步完成",
            }
        ),
        encoding="utf-8",
    )
    try:
        detail = await client.get(f"{BASE}/sync/jobs/{job_id}", headers=admin_headers)
        data = detail.json()["data"]
        assert data["status"] == "success"
        assert data["duration_ms"] == 71234
        assert data["message"] == "同步完成"

        # 任务已结束，可以再次触发
        again = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
        assert again.status_code == 200, again.text
    finally:
        result_path.unlink(missing_ok=True)


async def test_trigger_news_mode(
    client: AsyncClient, admin_headers: dict[str, str], no_spawn: None
) -> None:
    """资讯同步走同一个任务通道：模式被白名单接受，任务记录落库。"""
    resp = await client.post(f"{BASE}/sync", json={"mode": "news"}, headers=admin_headers)
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["data"]["mode"] == "news"


async def test_targeted_snapshot_sync_accepts_fund_codes(
    client: AsyncClient, admin_headers: dict[str, str], no_spawn: None
) -> None:
    response = await client.post(
        f"{BASE}/sync",
        json={"mode": "snapshot", "codes": "021180"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["mode"] == "snapshot"
    assert json.loads(data["params"])["codes"] == "021180"
