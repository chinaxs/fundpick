"""采集定时调度。

设计取舍：
- **分钟级轮询 + 当日去重**，不引入 cron 库：基金数据是 T+1 日频，
  "每周几的几点跑一次"足够，规则越简单越容易在后台核对。
- 多 worker 同时在线时，靠 `sync_jobs` 的数据库互斥 + 运行中检查天然去重；
  定时记录只在任务**真正启动后**才写 `last_run_on`，被拒绝的触发下一轮会重试。
- 调度只负责"按时开跑"，不负责保证数据完整——那由任务中心的计数与告警暴露。
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.sync_job import SyncSchedule
from app.schemas.sync_job import (
    SyncJobRead,
    SyncScheduleCreate,
    SyncScheduleRead,
    SyncScheduleUpdate,
    SyncTriggerRequest,
)
from app.services.sync_job import SyncJobService

logger = get_logger(__name__)

# 任务因"已有任务在跑"被顺延后，允许在计划时间后多久内补跑
CATCH_UP_HOURS = 6


class SyncScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[SyncScheduleRead]:
        rows = (
            await self.session.execute(select(SyncSchedule).order_by(SyncSchedule.hour))
        ).scalars()
        return [SyncScheduleRead.model_validate(row) for row in rows]

    async def create(self, payload: SyncScheduleCreate) -> SyncScheduleRead:
        schedule = SyncSchedule(
            mode=payload.mode,
            hour=payload.hour,
            minute=payload.minute,
            weekdays=payload.weekdays,
            enabled=payload.enabled,
        )
        self.session.add(schedule)
        await self.session.commit()
        await self.session.refresh(schedule)
        return SyncScheduleRead.model_validate(schedule)

    async def update(self, schedule_id: int, payload: SyncScheduleUpdate) -> SyncScheduleRead:
        schedule = await self.session.get(SyncSchedule, schedule_id)
        if schedule is None:
            raise NotFoundError("定时任务不存在")
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(schedule, field, value)
        await self.session.commit()
        await self.session.refresh(schedule)
        return SyncScheduleRead.model_validate(schedule)

    async def delete(self, schedule_id: int) -> None:
        schedule = await self.session.get(SyncSchedule, schedule_id)
        if schedule is None:
            raise NotFoundError("定时任务不存在")
        await self.session.delete(schedule)
        await self.session.commit()


def _scheduled_at(schedule: SyncSchedule, today: date) -> datetime:
    return datetime.combine(today, datetime.min.time()).replace(
        hour=schedule.hour, minute=schedule.minute
    )


def is_due(schedule: SyncSchedule, now: datetime) -> bool:
    """今天是否该跑：星期匹配、已过计划时间、未超补跑窗口、今天没跑过。"""
    if not schedule.enabled:
        return False
    if schedule.weekdays:
        weekdays = {int(day) for day in schedule.weekdays.split(",") if day}
        if now.isoweekday() not in weekdays:
            return False
    if schedule.last_run_on == now.date():
        return False
    target = _scheduled_at(schedule, now.date())
    if now < target:
        return False
    return now - target <= timedelta(hours=CATCH_UP_HOURS)


async def tick(now: datetime | None = None) -> list[SyncJobRead]:
    """跑一轮检查，返回本轮启动的任务（便于测试与日志）。"""
    now = now or datetime.now()
    started: list[SyncJobRead] = []
    async with async_session_factory() as session:
        schedule_ids = list(
            (await session.execute(select(SyncSchedule.id).where(SyncSchedule.enabled.is_(True))))
            .scalars()
            .all()
        )
        for schedule_id in schedule_ids:
            schedule = await session.get(SyncSchedule, schedule_id)
            if schedule is None or not is_due(schedule, now):
                continue
            try:
                job = await SyncJobService(session).start(
                    SyncTriggerRequest(mode=schedule.mode),
                    "scheduler",
                    schedule_id=schedule.id,
                    scheduled_on=now.date(),
                )
            except ConflictError:
                # 已有任务在跑，本轮跳过；last_run_on 不写，下一轮补跑
                logger.info("[调度] %s 未启动：已有任务在运行", schedule.mode)
                await session.rollback()
                continue
            except Exception as exc:  # 单条配置异常不影响其他配置
                logger.warning("[调度] %s 启动失败：%s", schedule.mode, exc)
                await session.rollback()
                continue
            logger.info("[调度] 已启动任务 #%s（%s）", job.id, schedule.mode)
            started.append(job)
    return started


async def run_scheduler(interval_seconds: int = 60) -> None:
    """常驻循环，由应用生命周期启动。"""
    logger.info("采集调度已启动，检查间隔 %s 秒", interval_seconds)
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # 调度本身不能因为一次异常退出
            logger.exception("[调度] 检查失败：%s", exc)
        await asyncio.sleep(interval_seconds)


__all__ = ["CATCH_UP_HOURS", "SyncScheduleService", "is_due", "run_scheduler", "tick"]
