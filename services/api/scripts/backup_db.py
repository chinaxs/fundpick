"""数据库备份 CLI。

    uv run python -m scripts.backup_db            # 备份并保留最近 14 份
    uv run python -m scripts.backup_db --keep 30
    uv run python -m scripts.backup_db --dry-run  # 只打印将执行的命令

设计要点：
- 密码走环境变量 `MYSQL_PWD`，不出现在进程列表里；
- `--single-transaction` 保证 InnoDB 一致性快照，不锁表；
- **流式**写盘：mysqldump 输出按块压缩进 `.tmp`，成功后再原子改名，
  既不把整库读进内存，也不会留下能被误用的半截文件；
- 同时维护 `backups/index.json` 清单（文件名、大小、SHA-256、时间），
  用于校验文件是否被改动。

备份文件存在只说明"当时导出了"，能不能恢复要靠 `scripts.restore_drill.py`。
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from app.core.config import settings

BACKUP_DIR = Path(__file__).resolve().parents[1] / "backups"
DEFAULT_KEEP = 14
INDEX_NAME = "index.json"
CHUNK = 64 * 1024


def backup_filename(now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{settings.MYSQL_DB}-{stamp}.sql.gz"


def dump_command() -> list[str]:
    return [
        "mysqldump",
        f"--host={settings.MYSQL_HOST}",
        f"--port={settings.MYSQL_PORT}",
        f"--user={settings.MYSQL_USER}",
        "--single-transaction",
        "--quick",
        "--skip-lock-tables",
        "--default-character-set=utf8mb4",
        settings.MYSQL_DB,
    ]


def prune(keep: int, directory: Path | None = None) -> list[str]:
    """删除超出保留数量的旧备份，返回被删除的文件名。"""
    directory = directory or BACKUP_DIR
    files = sorted(directory.glob("*.sql.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for path in files[keep:]:
        removed.append(path.name)
        path.unlink(missing_ok=True)
    return removed


def read_index(directory: Path | None = None) -> list[dict[str, object]]:
    path = (directory or BACKUP_DIR) / INDEX_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def file_sha256(path: Path) -> str:
    """压缩文件的 SHA-256。

    摘要对象必须与校验对象完全一致：这里算的是**落盘后的 .sql.gz 字节**，
    `restore_drill._checksum_matches` 也按同一份字节校验。
    早先对未压缩的 SQL 明文算摘要，导致"自己生成的备份过不了自己的校验"。
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def write_index(entry: dict[str, object], directory: Path | None = None) -> None:
    """清单原子写入：中途崩溃不能留下半截 JSON，让校验读到"没有清单"。"""
    directory = directory or BACKUP_DIR
    entries = [item for item in read_index(directory) if item.get("name") != entry.get("name")]
    entries.insert(0, entry)
    target = directory / INDEX_NAME
    tmp = target.with_name(f"{INDEX_NAME}.tmp")
    tmp.write_text(json.dumps(entries[:30], ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def run_backup(*, keep: int = DEFAULT_KEEP, dry_run: bool = False) -> dict[str, object]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / backup_filename()
    command = dump_command()
    if dry_run:
        return {"ok": True, "dry_run": True, "command": command, "target": str(target)}

    if shutil.which("mysqldump") is None:
        return {"ok": False, "error": "未找到 mysqldump，请安装 MySQL 客户端后重试"}

    env = os.environ.copy()
    if settings.MYSQL_PASSWORD:
        env["MYSQL_PWD"] = settings.MYSQL_PASSWORD

    tmp = target.with_name(f"{target.name}.tmp")
    err_path = target.with_name(f"{target.name}.err")
    started = datetime.now()
    dumped = 0
    try:
        with err_path.open("wb") as err_fh:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=err_fh,
                env=env,
            )
            assert proc.stdout is not None
            with gzip.open(tmp, "wb", compresslevel=6) as gz:
                while True:
                    chunk = proc.stdout.read(CHUNK)
                    if not chunk:
                        break
                    dumped += len(chunk)
                    gz.write(chunk)
            returncode = proc.wait()
        if returncode != 0:
            error = err_path.read_text(encoding="utf-8", errors="replace")[-800:]
            return {"ok": False, "error": error or "mysqldump 执行失败"}
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
        err_path.unlink(missing_ok=True)

    checksum = file_sha256(target)
    removed = prune(keep)
    write_index(
        {
            "name": target.name,
            "size_bytes": target.stat().st_size,
            "dump_bytes": dumped,
            "sha256": checksum,
            "sha256_of": "gzip",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return {
        "ok": True,
        "file": target.name,
        "size_bytes": target.stat().st_size,
        "sha256": checksum,
        "duration_ms": int((datetime.now() - started).total_seconds() * 1000),
        "removed": removed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="数据库备份")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP, help="保留最近几份备份")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不执行")
    args = parser.parse_args()

    result = run_backup(keep=args.keep, dry_run=args.dry_run)
    if not result.get("ok"):
        print(f"备份失败：{result.get('error')}", file=sys.stderr)
        raise SystemExit(1)
    if result.get("dry_run"):
        command = result.get("command")
        parts = command if isinstance(command, list) else []
        print("将执行：", " ".join(str(part) for part in parts))
        print("输出文件：", result["target"])
        return
    removed = result.get("removed")
    pruned = len(removed) if isinstance(removed, list) else 0
    print(
        f"备份完成：{result['file']}（{result['size_bytes']} 字节，"
        f"{result['duration_ms']} ms），清理 {pruned} 份旧备份"
    )


if __name__ == "__main__":
    main()
