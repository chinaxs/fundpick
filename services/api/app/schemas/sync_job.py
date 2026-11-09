"""后台数据同步：触发请求、任务读模型、定时配置与告警。"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.sync_modes import SYNC_MODES

__all__ = [
    "SYNC_MODES",
    "SyncAlert",
    "SyncFailureItem",
    "SyncJobRead",
    "SyncScheduleCreate",
    "SyncScheduleRead",
    "SyncScheduleUpdate",
    "SyncTriggerRequest",
]

_WEEKDAYS_PATTERN = re.compile(r"^[1-7](,[1-7])*$")


def _normalize_weekdays(value: str) -> str:
    """统一成升序去重的 "1,2,3,4,5"；空串表示每天。"""
    value = (value or "").strip()
    if not value:
        return ""
    if not _WEEKDAYS_PATTERN.fullmatch(value):
        raise ValueError("星期格式应为 1-7 的逗号分隔列表")
    days = sorted({int(part) for part in value.split(",")})
    return ",".join(str(day) for day in days)


class SyncTriggerRequest(BaseModel):
    mode: str = Field(default="quick", description="同步模式，与 CLI --mode 一致")
    limit: int | None = Field(default=None, ge=1, le=50000, description="限制处理数量")
    codes: str | None = Field(default=None, max_length=500, description="指定基金代码，逗号分隔")
    force: bool = Field(default=False, description="sector 模式下全量重算")


class SyncFailureItem(BaseModel):
    item: str = Field(description="失败对象，如基金代码")
    reason: str = Field(description="失败原因")


class SyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    params: str | None = None
    status: str
    triggered_by: str | None = None
    pid: int | None = None
    log_file: str | None = None

    # 进度
    phase: str | None = None
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[SyncFailureItem] = Field(default_factory=list)
    heartbeat_at: datetime | None = None

    # 控制
    cancel_requested: bool = False
    timeout_seconds: int = 1800

    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    message: str | None = None
    log_tail: str | None = None

    @field_validator("failures", mode="before")
    @classmethod
    def _parse_failures(cls, value: object) -> object:
        """数据库里是 JSON 字符串（或 NULL），接口对外给结构化数组。"""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            import json

            try:
                data = json.loads(value)
            except ValueError:
                return []
            if isinstance(data, list):
                return [
                    item
                    for item in data
                    if isinstance(item, dict) and {"item", "reason"} <= item.keys()
                ]
            return []
        return value


class SyncScheduleCreate(BaseModel):
    mode: str = Field(default="quick")
    hour: int = Field(default=18, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekdays: str = Field(default="1,2,3,4,5", description="ISO 星期，1=周一；空表示每天")
    enabled: bool = True

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        if value not in SYNC_MODES:
            raise ValueError("不支持的同步模式")
        return value

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: str) -> str:
        return _normalize_weekdays(value)


class SyncScheduleUpdate(BaseModel):
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    weekdays: str | None = None
    enabled: bool | None = None

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_weekdays(value)


class SyncScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    hour: int
    minute: int
    weekdays: str
    enabled: bool
    last_run_on: date | None = None
    last_job_id: int | None = None


class SyncAlert(BaseModel):
    level: str = Field(description="error / warning")
    job_id: int | None = None
    mode: str | None = None
    title: str
    detail: str
    at: str
