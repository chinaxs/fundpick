"""备份恢复演练。

    uv run python -m scripts.restore_drill              # 用最新备份演练
    uv run python -m scripts.restore_drill --file x.sql.gz

流程：校验清单 → 建**本次专用**临时库 → 流式导入 → 核对关键表 → 删临时库 → 写结果。

为什么必须演练：`mysqldump` 成功只代表导出没报错。备份损坏、字符集不兼容、
缺少建表语句这类问题，只有"真的恢复一次"才会暴露。

几个刻意的设计：
- 临时库名带时间戳与随机后缀，两个演练同时跑不会互相删库；
- 导入用管道流式传输，不把整份 SQL 读进内存；
- 无论成功失败都写 `backups/last_restore_drill.json`，
  后台健康度不会因为"这次失败没写结果"继续显示旧的成功记录；
- 只核对"表存在 + 基金表非空"，不拿行数和生产库比较：
  备份可能早于最近一次采集，行数不同是正常的。
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from scripts.backup_db import BACKUP_DIR, file_sha256, read_index

DRILL_PREFIX = f"{settings.MYSQL_DB}_drill"
CHECK_TABLES = (
    "funds",
    "fund_navs",
    "articles",
    "users",
    "fund_transactions",
    "trade_applications",
    "fund_portfolio_flows",
    # 会话表也要进清单：完整性检查要用它发现孤儿会话，
    # 不在清单里就只能跳过，等于没检查。
    "auth_sessions",
)

# 账本完整性核对：全部在**恢复后的临时库**里自查，并与备份时刻的清单摘要一起留痕。
# 刻意不拿行数和持续写入的生产库比较——备份可能早于最近一次采集，
# 行数不同是正常的，引用完整性才是"这份备份能不能用"的判据。
INTEGRITY_CHECKS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "交易记录指向的基金存在",
        "SELECT COUNT(*) FROM fund_transactions t "
        "LEFT JOIN funds f ON f.id = t.fund_id WHERE f.id IS NULL",
        ("funds", "fund_transactions"),
    ),
    (
        "公司行为指向的基金存在",
        "SELECT COUNT(*) FROM fund_portfolio_flows fl "
        "LEFT JOIN funds f ON f.id = fl.fund_id WHERE f.id IS NULL",
        ("funds", "fund_portfolio_flows"),
    ),
    (
        "已确认交易份额为正",
        "SELECT COUNT(*) FROM fund_transactions "
        "WHERE status = 'confirmed' AND (shares IS NULL OR shares <= 0)",
        ("fund_transactions",),
    ),
    (
        "待确认申请指向的基金存在",
        "SELECT COUNT(*) FROM trade_applications a "
        "LEFT JOIN funds f ON f.id = a.fund_id WHERE f.id IS NULL",
        ("funds", "trade_applications"),
    ),
    (
        "会员会话的主体存在",
        "SELECT COUNT(*) FROM auth_sessions s WHERE s.scope = 'portal' "
        "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = s.subject_id)",
        ("users", "auth_sessions"),
    ),
)
CHUNK = 64 * 1024


def _url(database: str) -> str:
    user = quote_plus(settings.MYSQL_USER)
    password = quote_plus(settings.MYSQL_PASSWORD)
    auth = f"{user}:{password}" if password else user
    return (
        f"mysql+asyncmy://{auth}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
        f"/{database}?charset=utf8mb4"
    )


def drill_database(now: datetime | None = None) -> str:
    """每次演练用独立库名，避免并发演练互相 DROP。"""
    stamp = (now or datetime.now()).strftime("%Y%m%d%H%M%S")
    return f"{DRILL_PREFIX}_{stamp}_{uuid.uuid4().hex[:6]}"


def latest_backup() -> Path | None:
    if not BACKUP_DIR.exists():
        return None
    files = sorted(BACKUP_DIR.glob("*.sql.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


async def _execute(database: str, sql: str) -> None:
    engine = create_async_engine(_url(database), future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


async def _table_counts(database: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    engine = create_async_engine(_url(database), future=True)
    try:
        async with engine.connect() as conn:
            for table in CHECK_TABLES:
                try:
                    query = text(f"SELECT COUNT(*) FROM `{table}`")
                    value = (await conn.execute(query)).scalar_one()
                    counts[table] = int(value or 0)
                except Exception:  # 表不存在也照实记录，不中断演练
                    counts[table] = -1
    finally:
        await engine.dispose()
    return counts


async def _integrity_checks(
    database: str, counts: dict[str, int]
) -> tuple[list[dict[str, object]], str | None]:
    """在恢复后的库里做引用完整性核对；返回（结果列表, 迁移版本）。

    缺表（老备份没有这张表）的检查记为 `None`（跳过），不算通过也不算失败。
    """
    results: list[dict[str, object]] = []
    version: str | None = None
    engine = create_async_engine(_url(database), future=True)
    try:
        async with engine.connect() as conn:
            for name, sql, required in INTEGRITY_CHECKS:
                # 注意用 `counts.get(table, -1)`：0 行是"表存在但为空"，
                # 必须照常检查；只有键缺失（-1）才是"表不存在"。
                if not all(counts.get(table, -1) >= 0 for table in required):
                    results.append({"name": name, "ok": None, "detail": "相关表不存在，跳过"})
                    continue
                try:
                    value = (await conn.execute(text(sql))).scalar_one()
                    results.append(
                        {
                            "name": name,
                            "ok": int(value or 0) == 0,
                            "detail": f"异常行数 {int(value or 0)}",
                        }
                    )
                except Exception as exc:  # 单条核对失败也要留痕，不中断其它检查
                    results.append({"name": name, "ok": False, "detail": str(exc)[:200]})
            try:
                version = (
                    await conn.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar_one_or_none()
            except Exception:
                version = None
    finally:
        await engine.dispose()
    return results, version


def _import_dump(backup: Path, database: str) -> str | None:
    """把备份流式导入临时库；返回错误信息，成功返回 None。"""
    if shutil.which("mysql") is None:
        return "未找到 mysql 客户端，请安装 MySQL 客户端后重试"
    env = os.environ.copy()
    if settings.MYSQL_PASSWORD:
        env["MYSQL_PWD"] = settings.MYSQL_PASSWORD

    err_path = BACKUP_DIR / f".import-{database}.err"
    try:
        with err_path.open("wb") as err_fh:
            proc = subprocess.Popen(
                [
                    "mysql",
                    f"--host={settings.MYSQL_HOST}",
                    f"--port={settings.MYSQL_PORT}",
                    f"--user={settings.MYSQL_USER}",
                    "--default-character-set=utf8mb4",
                    f"--database={database}",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=err_fh,
                env=env,
            )
            assert proc.stdin is not None
            try:
                with gzip.open(backup, "rb") as source:
                    while True:
                        chunk = source.read(CHUNK)
                        if not chunk:
                            break
                        proc.stdin.write(chunk)
                proc.stdin.close()
            except (OSError, gzip.BadGzipFile) as exc:
                proc.kill()
                return f"备份文件无法读取或解压：{exc}"
            returncode = proc.wait()
        if returncode != 0:
            error = err_path.read_text(encoding="utf-8", errors="replace")[-800:]
            return error or "mysql 导入失败"
        return None
    finally:
        err_path.unlink(missing_ok=True)


def _checksum_matches(backup: Path) -> bool | None:
    """对照同目录 index.json 校验 SHA-256；清单里没有该文件时返回 None。

    摘要按**压缩文件字节**计算，与 `backup_db.run_backup` 写清单时完全一致。
    清单按备份所在目录读取（而不是全局 BACKUP_DIR），演练指定任意目录都能校验。
    """
    for entry in read_index(backup.parent):
        if entry.get("name") != backup.name:
            continue
        expected = entry.get("sha256")
        if not isinstance(expected, str):
            return None
        return file_sha256(backup) == expected
    return None


async def drill(backup: Path) -> dict[str, object]:
    started = datetime.now()
    database = drill_database()
    result: dict[str, object] = {"ok": False, "file": backup.name, "database": database}
    created = False
    try:
        checksum = await asyncio.to_thread(_checksum_matches, backup)
        result["checksum_ok"] = checksum
        if checksum is False:
            # 摘要不符说明文件被截断/篡改：任何建库、导入都不要做，
            # 否则会把坏数据恢复进临时库，还可能因为"表非空"被误判为成功。
            result["error"] = "备份文件的 SHA-256 与清单不一致，已拒绝恢复"
            return result
        if checksum is None:
            # 无清单意味着"无法验证"，不能当成"完整性通过"
            result["checksum_status"] = "unverified"

        try:
            await _execute("mysql", f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4")
            created = True
        except Exception as exc:
            result["error"] = f"无法创建临时库：{exc}"
            return result

        error = await asyncio.to_thread(_import_dump, backup, database)
        if error:
            result["error"] = error
            return result

        counts = await _table_counts(database)
        result["tables"] = counts
        missing = [name for name, value in counts.items() if value < 0]
        if missing:
            result["error"] = f"恢复后缺少表：{', '.join(missing)}"
            return result
        if counts.get("funds", 0) <= 0:
            result["error"] = "恢复后基金表为空，可能导出了错误的库"
            return result

        integrity, version = await _integrity_checks(database, counts)
        result["integrity"] = integrity
        result["alembic_version"] = version
        result["sha256"] = checksum
        failed = [str(item["name"]) for item in integrity if item["ok"] is False]
        if failed:
            result["error"] = f"账本完整性核对未通过：{', '.join(failed)}"
            return result

        empty = [name for name, value in counts.items() if value == 0]
        if empty:
            result["warning"] = f"以下表恢复后为空：{', '.join(empty)}"
        result["ok"] = True
        return result
    finally:
        if created:
            try:
                await _execute("mysql", f"DROP DATABASE IF EXISTS `{database}`")
            except Exception as exc:  # 清理失败不影响结论，但要留痕
                result["cleanup_error"] = str(exc)
        result["finished_at"] = datetime.now().isoformat(timespec="seconds")
        result["duration_ms"] = int((datetime.now() - started).total_seconds() * 1000)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (BACKUP_DIR / "last_restore_drill.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="备份恢复演练")
    parser.add_argument("--file", type=str, default=None, help="指定备份文件，默认取最新一份")
    args = parser.parse_args()

    backup = Path(args.file) if args.file else latest_backup()
    if backup is None or not backup.exists():
        print("没有可用的备份文件，请先执行 scripts.backup_db", file=sys.stderr)
        raise SystemExit(1)

    result = asyncio.run(drill(backup))
    if not result.get("ok"):
        print(f"恢复演练失败：{result.get('error')}", file=sys.stderr)
        raise SystemExit(1)
    print(f"恢复演练通过：{result['file']}，耗时 {result['duration_ms']} ms")
    print("各表行数：", result.get("tables"))
    if result.get("warning"):
        print("提示：", result["warning"])


if __name__ == "__main__":
    main()
