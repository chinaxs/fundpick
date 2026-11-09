"""运维状态：日志文件、备份与恢复演练、汇总告警。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LogFileInfo(BaseModel):
    name: str
    size_bytes: int
    modified_at: datetime


class BackupInfo(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime
    total_backups: int
    restore_drill_at: datetime | None = None
    restore_drill_ok: bool | None = None


class OpsAlert(BaseModel):
    level: str = Field(description="error / warning")
    category: str = Field(description="data / sync / backup / logs")
    title: str
    detail: str


class OpsStatus(BaseModel):
    logs: list[LogFileInfo] = Field(default_factory=list)
    backup: BackupInfo | None = None
    alerts: list[OpsAlert] = Field(default_factory=list)
    checked_at: datetime
