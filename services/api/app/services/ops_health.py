"""运行健康度：日志留档、备份状态与告警汇总。

这里只做"读状态"，备份与恢复由 `scripts/backup_db.py` /
`scripts/restore_drill.py` 执行（需要 mysqldump 与真实数据库权限，
不适合放在 API 进程里跑）。后台只回答三个问题：

1. 日志还在不在、有多大（部署到容器时容易丢，需要显式检查）；
2. 最近一次备份是什么时候、有没有做过恢复演练；
3. 现在有没有需要人处理的事（数据滞后、采集失败、备份过期）。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LOG_DIR
from app.models.fund import Fund
from app.schemas.ops import BackupInfo, LogFileInfo, OpsAlert, OpsStatus
from app.services.sync_job import SyncJobService

API_DIR = LOG_DIR.parent
BACKUP_DIR = API_DIR / "backups"
# 备份超过该天数没有更新就告警
BACKUP_STALE_DAYS = 7
# 净值自然日龄超过该天数视为数据滞后（周末两天属正常）
NAV_STALE_DAYS = 4


def _file_info(path: Path) -> LogFileInfo | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return LogFileInfo(
        name=path.name,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime),
    )


def list_logs(limit: int = 12) -> list[LogFileInfo]:
    if not LOG_DIR.exists():
        return []
    files = [path for path in LOG_DIR.glob("*.log*") if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    infos = [_file_info(path) for path in files[:limit]]
    return [info for info in infos if info is not None]


def latest_backup() -> BackupInfo | None:
    """最新备份文件 + 最近一次恢复演练结果（演练文件由脚本写入）。"""
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(
        BACKUP_DIR.glob("*.sql.gz"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    if not backups:
        return None
    newest = backups[0]
    drill_file = BACKUP_DIR / "last_restore_drill.json"
    drill: dict[str, Any] | None = None
    if drill_file.exists():
        try:
            data = json.loads(drill_file.read_text(encoding="utf-8"))
            drill = data if isinstance(data, dict) else None
        except (OSError, ValueError):
            drill = None
    stat = newest.stat()
    return BackupInfo(
        name=newest.name,
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime),
        total_backups=len(backups),
        restore_drill_at=_parse_dt((drill or {}).get("finished_at")),
        restore_drill_ok=(drill or {}).get("ok") if drill else None,
    )


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class OpsHealthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def status(self) -> OpsStatus:
        alerts = await self.alerts()
        return OpsStatus(
            logs=list_logs(),
            backup=latest_backup(),
            alerts=alerts,
            checked_at=datetime.now(),
        )

    async def alerts(self) -> list[OpsAlert]:
        alerts: list[OpsAlert] = []

        # 1. 净值数据滞后
        latest_nav: date | None = (
            await self.session.execute(select(func.max(Fund.latest_nav_date)))
        ).scalar_one()
        if latest_nav is None:
            alerts.append(
                OpsAlert(
                    level="warning",
                    category="data",
                    title="没有可用的最新净值",
                    detail="funds.latest_nav_date 全为空，请先跑一次基础数据同步。",
                )
            )
        else:
            lag = (date.today() - latest_nav).days
            if lag > NAV_STALE_DAYS:
                alerts.append(
                    OpsAlert(
                        level="error",
                        category="data",
                        title=f"净值已滞后 {lag} 天",
                        detail=f"最新净值日期 {latest_nav.isoformat()}，请检查采集任务与数据源。",
                    )
                )

        # 2. 采集任务失败/超时/卡住
        for item in await SyncJobService(self.session).alerts(24):
            alerts.append(
                OpsAlert(
                    level="error" if item["level"] == "error" else "warning",
                    category="sync",
                    title=str(item["title"]),
                    detail=str(item["detail"]),
                )
            )

        # 3. 备份
        backup = latest_backup()
        if backup is None:
            alerts.append(
                OpsAlert(
                    level="warning",
                    category="backup",
                    title="还没有数据库备份",
                    detail="执行 `uv run python -m scripts.backup_db` 生成第一份备份。",
                )
            )
        else:
            age = (datetime.now() - backup.created_at).days
            if age > BACKUP_STALE_DAYS:
                alerts.append(
                    OpsAlert(
                        level="error",
                        category="backup",
                        title=f"最近备份已 {age} 天未更新",
                        detail=f"最新备份 {backup.name}，建议把备份加入每日调度。",
                    )
                )
            if backup.restore_drill_ok is False:
                alerts.append(
                    OpsAlert(
                        level="error",
                        category="backup",
                        title="最近一次恢复演练失败",
                        detail="备份可用性未验证，请查看 backups/last_restore_drill.json。",
                    )
                )
            elif backup.restore_drill_at is None:
                alerts.append(
                    OpsAlert(
                        level="warning",
                        category="backup",
                        title="还没有做过恢复演练",
                        detail=(
                            "备份存在不代表能恢复：运行 `uv run python -m scripts.restore_drill`。"
                        ),
                    )
                )

        # 4. 日志文件缺失（容器重建常见）
        if not list_logs(1):
            alerts.append(
                OpsAlert(
                    level="warning",
                    category="logs",
                    title="没有找到日志文件",
                    detail="请确认 LOG_FILE_ENABLED 未被关闭，且 logs 目录已挂载持久卷。",
                )
            )

        return alerts
