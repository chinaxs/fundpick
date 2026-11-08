"""采集任务生命周期：逐只取消/失败计数，以及重启后的超时收敛。"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.job_progress import JobProgress, SyncCancelled, cancel_path, request_cancel
from app.models.sync_job import SyncJob
from app.services import sync_job
from app.services.sync_job import SyncJobService
from scripts import sync_funds


class _Provider:
    """最小 provider：可配置成"全部成功"或"全部失败"。"""

    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def fund_profile(self, code: str):
        self.calls += 1
        if self.fail:
            raise RuntimeError("上游超时")
        return None

    def fund_holdings(self, code: str, year: str):
        self.calls += 1
        if self.fail:
            raise RuntimeError("上游超时")
        return []


@pytest.fixture
def job_id() -> int:
    value = 900000 + uuid4().int % 1000
    yield value
    cancel_path(value).unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _reset_progress():
    original = sync_funds.PROGRESS
    yield
    sync_funds.PROGRESS = original


async def test_detail_reports_failures(job_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Provider(fail=True)
    monkeypatch.setattr(sync_funds, "get_provider", lambda: provider)
    sync_funds.PROGRESS = JobProgress(job_id)

    async with sync_funds.async_session_factory() as session:
        updated = await sync_funds.sync_details(session, None, ["000003"])

    assert updated == 0
    assert sync_funds.PROGRESS.failed >= 1
    assert sync_funds.PROGRESS.failures[0]["reason"].startswith("上游超时")


async def test_holdings_stops_at_checkpoint(job_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Provider()
    monkeypatch.setattr(sync_funds, "get_provider", lambda: provider)
    sync_funds.PROGRESS = JobProgress(job_id)
    request_cancel(job_id)  # 模拟后台点了取消

    async with sync_funds.async_session_factory() as session:
        with pytest.raises(SyncCancelled):
            await sync_funds.sync_holdings(session, None, ["000003"])
    assert provider.calls == 0  # 进循环先检查，没打上游


async def test_detail_stops_at_checkpoint(job_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Provider()
    monkeypatch.setattr(sync_funds, "get_provider", lambda: provider)
    sync_funds.PROGRESS = JobProgress(job_id)
    request_cancel(job_id)

    async with sync_funds.async_session_factory() as session:
        with pytest.raises(SyncCancelled):
            await sync_funds.sync_details(session, None, ["000003"])
    assert provider.calls == 0


async def test_alive_pid_beyond_timeout_is_terminated(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API 重启后没有 watcher，超时的存活进程要在查询时收敛。"""
    terminated: list[int] = []

    async def fake_terminate(self, job) -> bool:
        terminated.append(job.pid)
        return True

    monkeypatch.setattr(SyncJobService, "_terminate", fake_terminate)

    async with sync_funds.async_session_factory() as session:
        job = SyncJob(
            mode="quick",
            status="running",
            triggered_by="admin",
            pid=os.getpid(),
            timeout_seconds=60,
            started_at=datetime.now() - timedelta(hours=1),
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

        service = SyncJobService(session)
        read = await service.get(job_id)

    assert read.status == "timeout"
    assert terminated == [os.getpid()]
    assert "超时" in (read.message or "") or "超过" in (read.message or "")

    from sqlalchemy import delete

    async with sync_funds.async_session_factory() as session:
        await session.execute(delete(SyncJob).where(SyncJob.id == job_id))
        await session.commit()


class _Job:
    """最小任务替身：`_reconcile` 只读这几个字段。"""

    def __init__(self, pid: int, *, timeout: int = 1) -> None:
        self.id = 999998
        self.status = "running"
        self.pid = pid
        self.timeout_seconds = timeout
        self.started_at = datetime.now() - timedelta(seconds=30)
        self.cancel_requested = False
        self.log_file = None
        self.message: str | None = None
        self.finished_at = None


def test_pid_belongs_rejects_other_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """命令行是另一个 job-id 的采集进程时，绝不能按历史 PID 去杀。"""

    def fake_field(pid: int, field: str) -> str | None:
        if field == "command":
            return "python -m scripts.sync_funds --mode quick --job-id 42"
        return None

    monkeypatch.setattr(sync_job, "_ps_field", fake_field)
    assert sync_job._pid_belongs(123, _Job(123)) is False
    other = SimpleNamespace(id=42, started_at=None)
    assert sync_job._pid_belongs(123, other) is True


async def test_terminate_refuses_to_kill_foreign_process(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:

        def fake_field(pid: int, field: str) -> str | None:
            if field == "command":
                return "python -m scripts.sync_funds --mode quick --job-id 4242"
            return None

        monkeypatch.setattr(sync_job, "_ps_field", fake_field)
        service = SyncJobService(AsyncMock())
        assert await service._terminate(_Job(proc.pid)) is False
        assert proc.poll() is None  # 没有被误杀
    finally:
        proc.kill()
        proc.wait(timeout=5)


async def test_reconcile_marks_timeout_when_process_already_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """进程已经退出时不必发信号，直接落超时终态。"""
    job = _Job(0)
    job.pid = 999999997  # 一定不存在的 PID
    service = SyncJobService(AsyncMock())
    monkeypatch.setattr(sync_job, "_read_result", lambda _: None)
    monkeypatch.setattr(service, "_apply_progress", AsyncMock())

    await service._reconcile(job)
    assert job.status == "timeout"
    assert job.finished_at is not None


async def test_unknown_process_identity_keeps_job_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """读不到命令行时不认领、不发信号：保留运行中并提示人工核对。"""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        monkeypatch.setattr(sync_job, "_ps_field", lambda pid, field: None)
        service = SyncJobService(AsyncMock())
        monkeypatch.setattr(sync_job, "_read_result", lambda _: None)
        monkeypatch.setattr(service, "_apply_progress", AsyncMock())

        job = _Job(proc.pid)
        await service._reconcile(job)

        assert job.status == "running"
        assert proc.poll() is None  # 没被误杀
        assert "人工" in (job.message or "")
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_pid_belongs_ignores_script_name_in_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--label scripts.sync_funds` 只是普通参数，不能据此认领进程。"""

    def fake_field(pid: int, field: str) -> str | None:
        if field == "command":
            return "python /opt/report.py --label scripts.sync_funds --job-id 42"
        return None

    monkeypatch.setattr(sync_job, "_ps_field", fake_field)
    assert sync_job._pid_belongs(123, _Job(123)) is False


def test_pid_entry_reads_module_and_script_only() -> None:
    assert sync_job._pid_entry(["python", "-m", "scripts.sync_funds", "--job-id", "7"]) == (
        "scripts.sync_funds"
    )
    assert sync_job._pid_entry(["python", "scripts/sync_news.py", "--job-id", "7"]) == (
        "scripts/sync_news.py"
    )
    assert sync_job._pid_entry(["python", "-c", "print(1)"]) is None
    assert sync_job._pid_entry(["/usr/local/bin/redis-server", "*:6379"]) is None
