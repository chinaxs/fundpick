"""运维状态：日志留档、备份状态、告警与备份文件维护。"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services import ops_health
from scripts import backup_db

BASE = "/api/v1/admin/system/health"


@pytest.fixture
def workdir() -> Iterator[Path]:
    """在仓库内的 logs 下建临时目录。

    不用 pytest 的 tmp_path：沙箱环境下基础临时目录可能建不出来，
    而 logs 目录本身就是这个模块要观察的对象，放这里更贴近真实路径。
    """
    path = Path(__file__).resolve().parents[1] / "logs" / f"_test_ops_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


async def _admin(client: AsyncClient) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/admin/auth/login", json={"username": "admin", "password": "Admin@123456"}
    )
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def test_health_requires_login(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


async def test_health_reports_logs_backup_and_alerts(
    client: AsyncClient, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs = workdir / "logs"
    logs.mkdir()
    (logs / "fundpick-api.log").write_text("x" * 128, encoding="utf-8")
    backups = workdir / "backups"
    backups.mkdir()
    backup_file = backups / "test_study-20261108-030000.sql.gz"
    backup_file.write_bytes(b"fake")
    (backups / "last_restore_drill.json").write_text(
        json.dumps({"ok": True, "finished_at": "2026-11-08T03:05:00"}), encoding="utf-8"
    )

    monkeypatch.setattr(ops_health, "LOG_DIR", logs)
    monkeypatch.setattr(ops_health, "BACKUP_DIR", backups)

    admin = await _admin(client)
    resp = await client.get(BASE, headers=admin)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["logs"][0]["name"] == "fundpick-api.log"
    assert data["logs"][0]["size_bytes"] == 128
    assert data["backup"]["name"] == "test_study-20261108-030000.sql.gz"
    assert data["backup"]["restore_drill_ok"] is True
    # 备份与日志都齐备时，不应再报这两类告警
    categories = {alert["category"] for alert in data["alerts"]}
    assert "backup" not in categories
    assert "logs" not in categories


async def test_health_warns_when_nothing_is_prepared(
    client: AsyncClient, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ops_health, "LOG_DIR", workdir / "no-logs")
    monkeypatch.setattr(ops_health, "BACKUP_DIR", workdir / "no-backups")

    admin = await _admin(client)
    alerts = (await client.get(BASE, headers=admin)).json()["data"]["alerts"]
    titles = [alert["title"] for alert in alerts]
    assert "还没有数据库备份" in titles
    assert "没有找到日志文件" in titles


def test_stale_backup_is_reported(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backups = workdir / "backups"
    backups.mkdir()
    old = backups / "old.sql.gz"
    old.write_bytes(b"x")
    stale = (datetime.now() - timedelta(days=30)).timestamp()
    os.utime(old, (stale, stale))
    monkeypatch.setattr(ops_health, "BACKUP_DIR", backups)

    info = ops_health.latest_backup()
    assert info is not None
    assert (datetime.now() - info.created_at).days >= 29


def test_prune_keeps_newest(workdir: Path) -> None:
    for index in range(5):
        path = workdir / f"db-2026110{index}-000000.sql.gz"
        path.write_bytes(b"x")
        stamp = (datetime.now() - timedelta(days=5 - index)).timestamp()
        os.utime(path, (stamp, stamp))

    removed = backup_db.prune(2, workdir)
    assert len(removed) == 3
    remaining = sorted(path.name for path in workdir.glob("*.sql.gz"))
    assert remaining == ["db-20261103-000000.sql.gz", "db-20261104-000000.sql.gz"]


def test_backup_filename_shape() -> None:
    name = backup_db.backup_filename(datetime(2026, 11, 8, 3, 0, 0))
    assert name.endswith("-20261108-030000.sql.gz")
    assert name.startswith(settings.MYSQL_DB)


# ---------------------------------------------------------------- 备份与演练


def test_backup_requires_mysql_client(monkeypatch: pytest.MonkeyPatch, workdir: Path) -> None:
    monkeypatch.setattr(backup_db, "BACKUP_DIR", workdir / "backups")
    monkeypatch.setattr(backup_db.shutil, "which", lambda name: None)
    result = backup_db.run_backup(keep=2)
    assert result["ok"] is False
    assert "mysqldump" in str(result["error"])
    # 失败不得留下半截备份文件
    assert list((workdir / "backups").glob("*.sql.gz")) == []


def test_backup_dry_run_does_not_touch_disk(monkeypatch: pytest.MonkeyPatch, workdir: Path) -> None:
    monkeypatch.setattr(backup_db, "BACKUP_DIR", workdir / "backups")
    result = backup_db.run_backup(dry_run=True)
    assert result["ok"] is True
    assert result["command"][0] == "mysqldump"
    assert not (workdir / "backups" / "index.json").exists()


def test_index_keeps_latest_entry(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backup_db, "BACKUP_DIR", workdir)
    backup_db.write_index({"name": "a.sql.gz", "sha256": "1"})
    backup_db.write_index({"name": "b.sql.gz", "sha256": "2"})
    backup_db.write_index({"name": "a.sql.gz", "sha256": "3"})
    entries = backup_db.read_index(workdir)
    assert [item["name"] for item in entries] == ["a.sql.gz", "b.sql.gz"]
    assert entries[0]["sha256"] == "3"


def test_drill_database_is_unique() -> None:
    from scripts.restore_drill import drill_database

    names = {drill_database() for _ in range(5)}
    assert len(names) == 5
    assert all(name.startswith(f"{settings.MYSQL_DB}_drill_") for name in names)


async def test_drill_writes_result_even_when_create_fails(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import restore_drill

    backups = workdir / "backups"
    backups.mkdir(parents=True)
    backup = backups / "test_study-20261108-000000.sql.gz"
    backup.write_bytes(b"not-a-real-dump")
    monkeypatch.setattr(restore_drill, "BACKUP_DIR", backups)

    async def fail_create(database: str, sql: str) -> None:
        raise RuntimeError("permission denied")

    monkeypatch.setattr(restore_drill, "_execute", fail_create)
    result = await restore_drill.drill(backup)

    assert result["ok"] is False
    assert "无法创建临时库" in str(result["error"])
    written = json.loads((backups / "last_restore_drill.json").read_text(encoding="utf-8"))
    assert written["ok"] is False
    assert written["database"].startswith(f"{settings.MYSQL_DB}_drill_")


async def test_drill_rejects_empty_fund_table(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import restore_drill

    backups = workdir / "backups"
    backups.mkdir(parents=True)
    backup = backups / "empty.sql.gz"
    backup.write_bytes(b"x")
    monkeypatch.setattr(restore_drill, "BACKUP_DIR", backups)

    async def ok_execute(database: str, sql: str) -> None:
        return None

    async def zero_counts(database: str) -> dict[str, int]:
        return dict.fromkeys(restore_drill.CHECK_TABLES, 0)

    def no_import(backup_path, database):
        # 真实实现是同步函数（在线程里跑），桩也必须同步
        return None

    monkeypatch.setattr(restore_drill, "_execute", ok_execute)
    monkeypatch.setattr(restore_drill, "_table_counts", zero_counts)
    monkeypatch.setattr(restore_drill, "_import_dump", no_import)

    result = await restore_drill.drill(backup)
    assert result["ok"] is False
    assert "基金表为空" in str(result["error"])


class _DumpProcess:
    def __init__(self, payload: bytes) -> None:
        import io

        self.stdout = io.BytesIO(payload)
        self.returncode = 0

    def wait(self) -> int:
        return 0


def _fake_popen(monkeypatch: pytest.MonkeyPatch, payload: bytes = b"SELECT 1;\n") -> None:
    """只替换 backup_db 里的 subprocess 引用，避免动到全局 subprocess。"""
    import subprocess
    from types import SimpleNamespace

    monkeypatch.setattr(
        backup_db,
        "subprocess",
        SimpleNamespace(Popen=lambda *a, **k: _DumpProcess(payload), PIPE=subprocess.PIPE),
    )


def _write_backup(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from scripts import restore_drill

    monkeypatch.setattr(backup_db, "BACKUP_DIR", workdir)
    monkeypatch.setattr(backup_db.shutil, "which", lambda _: "/fake/mysqldump")
    monkeypatch.setattr(restore_drill, "BACKUP_DIR", workdir)
    _fake_popen(monkeypatch)
    result = backup_db.run_backup()
    assert result["ok"] is True
    return workdir / str(result["file"])


def test_backup_checksum_matches_written_file(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """摘要按压缩文件字节计算，生成的备份必须能通过自己的校验。"""
    from scripts import restore_drill

    backup = _write_backup(workdir, monkeypatch)
    assert restore_drill._checksum_matches(backup) is True


def test_checksum_detects_tampering_and_truncation(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import restore_drill

    backup = _write_backup(workdir, monkeypatch)
    original = backup.read_bytes()

    backup.write_bytes(original[:-5])  # 截断
    assert restore_drill._checksum_matches(backup) is False

    backup.write_bytes(original + b"tampered")
    assert restore_drill._checksum_matches(backup) is False

    backup.write_bytes(original)
    assert restore_drill._checksum_matches(backup) is True


def test_checksum_reports_unverified_without_index(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """没有清单只能说"未验证"，不能当成完整性通过。"""
    from scripts import restore_drill

    backup = workdir / "orphan.sql.gz"
    backup.write_bytes(b"x")
    assert restore_drill._checksum_matches(backup) is None


async def test_drill_marks_unverified_without_index(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import restore_drill

    backup = workdir / "orphan.sql.gz"
    backup.write_bytes(b"x")
    monkeypatch.setattr(restore_drill, "BACKUP_DIR", workdir)

    async def ok_execute(database: str, sql: str) -> None:
        return None

    async def counts(database: str) -> dict[str, int]:
        return dict.fromkeys(restore_drill.CHECK_TABLES, 1)

    async def integrity(database: str, table_counts: dict[str, int]):
        return [], "i9c4e1f82a37"

    monkeypatch.setattr(restore_drill, "_execute", ok_execute)
    monkeypatch.setattr(restore_drill, "_table_counts", counts)
    monkeypatch.setattr(restore_drill, "_import_dump", lambda *args: None)
    monkeypatch.setattr(restore_drill, "_integrity_checks", integrity)

    result = await restore_drill.drill(backup)
    assert result["ok"] is True
    assert result["checksum_ok"] is None
    assert result["checksum_status"] == "unverified"
    assert result["alembic_version"] == "i9c4e1f82a37"


async def test_drill_rejects_broken_ledger_integrity(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """引用完整性不过必须判失败，不能只因为"表非空"就报恢复成功。"""
    from scripts import restore_drill

    backup = workdir / "ok.sql.gz"
    backup.write_bytes(b"x")
    monkeypatch.setattr(restore_drill, "BACKUP_DIR", workdir)

    async def ok_execute(database: str, sql: str) -> None:
        return None

    async def counts(database: str) -> dict[str, int]:
        return dict.fromkeys(restore_drill.CHECK_TABLES, 5)

    async def integrity(database: str, table_counts: dict[str, int]):
        return [{"name": "交易记录指向的基金存在", "ok": False, "detail": "异常行数 3"}], "head"

    monkeypatch.setattr(restore_drill, "_execute", ok_execute)
    monkeypatch.setattr(restore_drill, "_table_counts", counts)
    monkeypatch.setattr(restore_drill, "_import_dump", lambda *args: None)
    monkeypatch.setattr(restore_drill, "_integrity_checks", integrity)

    result = await restore_drill.drill(backup)
    assert result["ok"] is False
    assert "完整性" in str(result["error"])


async def test_integrity_checks_do_not_skip_existing_empty_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """表存在但 0 行仍要核对；只有键缺失才算缺表跳过。"""

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, sql):
            value = 1 if "auth_sessions" in str(sql) else 0
            return type(
                "Result",
                (),
                {"scalar_one": lambda self: value, "scalar_one_or_none": lambda self: None},
            )()

    class Engine:
        def connect(self):
            return Connection()

        async def dispose(self):
            return None

    from scripts import restore_drill

    monkeypatch.setattr(restore_drill, "create_async_engine", lambda *a, **k: Engine())
    counts = dict.fromkeys(restore_drill.CHECK_TABLES, 0)
    counts["funds"] = 1
    counts["auth_sessions"] = 1
    results, _ = await restore_drill._integrity_checks("isolated", counts)
    sessions = next(item for item in results if item["name"] == "会员会话的主体存在")
    assert sessions["ok"] is False
