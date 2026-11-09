"""采集任务中心：进度回填、取消、重试、超时、告警与定时调度。

子进程统一 mock 掉，测试只验证状态机与文件协议。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.session import async_session_factory
from app.job_progress import cancel_path, read_cancel_requested, request_cancel
from app.models.sync_job import SyncJob, SyncSchedule
from app.services.sync_job import LOG_DIR, SyncJobService
from app.services.sync_schedule import is_due, tick

PASSWORD = "Admin@123456"
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
    async def fake_spawn(self, job, payload):
        job.pid = os.getpid()
        await self.session.commit()

    monkeypatch.setattr(SyncJobService, "spawn", fake_spawn)


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    async with async_session_factory() as session:
        await session.execute(
            delete(SyncJob).where(
                SyncJob.triggered_by.in_(["admin", "scheduler"]), SyncJob.pid == os.getpid()
            )
        )
        await session.execute(delete(SyncSchedule).where(SyncSchedule.mode.in_(["quick", "news"])))
        await session.commit()


def _write(path, payload: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


async def test_progress_file_updates_counts(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(f"{BASE}/sync", json={"mode": "risk"}, headers=admin_headers)
    job_id = created.json()["data"]["id"]
    progress = LOG_DIR / f"sync_job_{job_id}.progress.json"
    _write(
        progress,
        {
            "phase": "risk",
            "total": 100,
            "succeeded": 62,
            "failed": 3,
            "skipped": 5,
            "failures": [
                {"item": "000001", "reason": "上游超时"},
                {"item": "000002", "reason": "无风险数据"},
            ],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    try:
        detail = await client.get(f"{BASE}/sync/jobs/{job_id}", headers=admin_headers)
        data = detail.json()["data"]
        assert data["phase"] == "risk"
        assert (data["total"], data["succeeded"], data["failed"], data["skipped"]) == (
            100,
            62,
            3,
            5,
        )
        assert [item["item"] for item in data["failures"]] == ["000001", "000002"]
        assert data["heartbeat_at"] is not None
    finally:
        progress.unlink(missing_ok=True)


async def test_cancel_running_job_sets_marker(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
    job_id = created.json()["data"]["id"]

    resp = await client.post(f"{BASE}/sync/jobs/{job_id}/cancel", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["cancel_requested"] is True
    assert data["status"] == "running"
    assert "取消" in (data["message"] or "")
    assert read_cancel_requested(job_id)
    cancel_path(job_id).unlink(missing_ok=True)


async def test_cancel_finished_job_conflict(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
    job_id = created.json()["data"]["id"]
    result = LOG_DIR / f"sync_job_{job_id}.result.json"
    _write(result, {"status": "success", "message": "同步完成"})
    try:
        resp = await client.post(f"{BASE}/sync/jobs/{job_id}/cancel", headers=admin_headers)
        assert resp.status_code == 409
    finally:
        result.unlink(missing_ok=True)


async def test_retry_reuses_params_as_new_job(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(
        f"{BASE}/sync", json={"mode": "risk", "limit": 10}, headers=admin_headers
    )
    original = created.json()["data"]
    result = LOG_DIR / f"sync_job_{original['id']}.result.json"
    _write(result, {"status": "failed", "message": "上游超时"})
    try:
        retried = await client.post(
            f"{BASE}/sync/jobs/{original['id']}/retry", headers=admin_headers
        )
        assert retried.status_code == 200, retried.text
        job = retried.json()["data"]
        assert job["id"] != original["id"]
        assert job["mode"] == "risk"
        assert json.loads(job["params"]) == {"limit": 10}

        # 原记录保持不可变，便于回溯
        detail = await client.get(f"{BASE}/sync/jobs/{original['id']}", headers=admin_headers)
        assert detail.json()["data"]["status"] == "failed"
    finally:
        result.unlink(missing_ok=True)


async def test_retry_rejected_while_running(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(f"{BASE}/sync", json={"mode": "quick"}, headers=admin_headers)
    job_id = created.json()["data"]["id"]
    resp = await client.post(f"{BASE}/sync/jobs/{job_id}/retry", headers=admin_headers)
    assert resp.status_code == 409


async def test_stale_running_job_becomes_timeout(client: AsyncClient, admin_headers: dict) -> None:
    async with async_session_factory() as session:
        job = SyncJob(
            mode="quick",
            status="running",
            triggered_by="admin",
            timeout_seconds=60,
            started_at=datetime.now() - timedelta(hours=2),
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    detail = await client.get(f"{BASE}/sync/jobs/{job_id}", headers=admin_headers)
    data = detail.json()["data"]
    assert data["status"] == "timeout"
    assert "超时" in data["message"]


async def test_alerts_surface_failed_jobs(
    client: AsyncClient, admin_headers: dict, no_spawn: None
) -> None:
    created = await client.post(f"{BASE}/sync", json={"mode": "news"}, headers=admin_headers)
    job_id = created.json()["data"]["id"]
    result = LOG_DIR / f"sync_job_{job_id}.result.json"
    _write(result, {"status": "failed", "message": "采集源不可用"})
    try:
        resp = await client.get(f"{BASE}/sync/alerts", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        alerts = resp.json()["data"]
        assert any(a["job_id"] == job_id and a["level"] == "error" for a in alerts)
    finally:
        result.unlink(missing_ok=True)


async def test_schedule_crud(client: AsyncClient, admin_headers: dict) -> None:
    created = await client.post(
        f"{BASE}/sync/schedules",
        json={"mode": "news", "hour": 9, "minute": 30, "weekdays": "5,1,1"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    schedule = created.json()["data"]
    # 星期去重并升序
    assert schedule["weekdays"] == "1,5"
    schedule_id = schedule["id"]

    listing = await client.get(f"{BASE}/sync/schedules", headers=admin_headers)
    assert schedule_id in [row["id"] for row in listing.json()["data"]]

    updated = await client.patch(
        f"{BASE}/sync/schedules/{schedule_id}", json={"enabled": False}, headers=admin_headers
    )
    assert updated.json()["data"]["enabled"] is False

    invalid = await client.post(
        f"{BASE}/sync/schedules",
        json={"mode": "quick", "hour": 9, "minute": 0, "weekdays": "0,8"},
        headers=admin_headers,
    )
    assert invalid.status_code == 422

    removed = await client.delete(f"{BASE}/sync/schedules/{schedule_id}", headers=admin_headers)
    assert removed.status_code == 200
    missing = await client.patch(
        f"{BASE}/sync/schedules/{schedule_id}", json={"enabled": True}, headers=admin_headers
    )
    assert missing.status_code == 404


def _schedule(**overrides) -> SyncSchedule:
    values = {
        "mode": "quick",
        "hour": 18,
        "minute": 30,
        "weekdays": "1,2,3,4,5",
        "enabled": True,
        "last_run_on": None,
    }
    values.update(overrides)
    return SyncSchedule(**values)


def test_is_due_respects_weekday_time_and_history() -> None:
    friday = datetime(2026, 11, 6, 18, 31)  # 周五，已过 18:30
    assert is_due(_schedule(), friday)
    assert is_due(_schedule(weekdays=""), friday)
    assert not is_due(_schedule(weekdays="6,7"), friday)
    assert not is_due(_schedule(enabled=False), friday)
    assert not is_due(_schedule(), datetime(2026, 11, 6, 18, 0))
    assert not is_due(_schedule(last_run_on=friday.date()), friday)
    # 超过补跑窗口（6 小时）不再补，避免服务长时间停机后开机即全量重跑
    assert not is_due(_schedule(hour=1, minute=0), datetime(2026, 11, 6, 8, 0))


async def test_tick_starts_due_schedule_once(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, admin_headers: dict
) -> None:
    async def fake_spawn(self, job, payload):
        job.pid = os.getpid()
        await self.session.commit()

    monkeypatch.setattr(SyncJobService, "spawn", fake_spawn)

    now = datetime.now().replace(second=0, microsecond=0)
    async with async_session_factory() as session:
        schedule = SyncSchedule(
            mode="quick",
            hour=now.hour,
            minute=now.minute,
            weekdays=str(now.isoweekday()),
            enabled=True,
        )
        session.add(schedule)
        await session.commit()
        await session.refresh(schedule)
        schedule_id = schedule.id

    started = await tick(now)
    assert [job.mode for job in started] == ["quick"]

    # 同一天再跑不会重复触发
    assert await tick(now) == []

    async with async_session_factory() as session:
        row = await session.get(SyncSchedule, schedule_id)
        assert row is not None
        assert row.last_run_on == now.date()
        assert row.last_job_id == started[0].id


async def test_cancel_pending_job_without_process(client: AsyncClient, admin_headers: dict) -> None:
    """子进程还没起来（无 PID）时取消，直接收敛为已取消，不用等宽限期。"""
    async with async_session_factory() as session:
        job = SyncJob(mode="quick", status="starting", triggered_by="admin")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    request_cancel(job_id)
    resp = await client.post(f"{BASE}/sync/jobs/{job_id}/cancel", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"
    cancel_path(job_id).unlink(missing_ok=True)


async def test_progress_endpoint_requires_login(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/sync/schedules")).status_code == 401
    assert (await client.post(f"{BASE}/sync/jobs/1/cancel")).status_code == 401
