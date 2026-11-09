"""后台数据同步任务服务。

为什么用独立子进程：
`scripts/sync_funds.py` 的 `run()` 结尾会 `dispose_engine()`，且用 `asyncio.run()`
新建事件循环；若在 API 进程内直接调用，会销毁 API 自己的连接池并触发跨 loop 错误。
因此这里用 `asyncio.create_subprocess_exec` 起独立进程，脚本通过 `--job-id`
写结果文件，API 侧 watcher / 轮询据此回填 `sync_jobs`，即使 API 重启也能恢复状态。

任务状态机：

```
starting ──进程启动──> running ──┬─> success            全部成功
                                 ├─> partial_success    有失败条目但主体完成
                                 ├─> failed             进程异常或整体失败
                                 ├─> cancelled          收到取消并在检查点退出
                                 └─> timeout            超过 timeout_seconds
```

进度与取消走 `app/job_progress.py` 的文件协议，理由见该模块说明。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from datetime import date, datetime, timedelta
from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.job_progress import (
    LOG_DIR,
    clear_control_files,
    progress_path,
    read_cancel_requested,
    read_progress,
    request_cancel,
    result_path,
)
from app.models.sync_job import SyncJob, SyncJobMutex, SyncSchedule
from app.schemas.sync_job import SyncJobRead, SyncTriggerRequest
from app.sync_modes import SYNC_MODES

logger = get_logger(__name__)
API_DIR = LOG_DIR.parent
# 保活 watcher，防止事件循环把没有强引用的 task 回收
_WATCHERS: set[asyncio.Task] = set()
ACTIVE_STATUSES = ("starting", "running")
TERMINAL_STATUSES = ("success", "partial_success", "failed", "cancelled", "timeout")

# 不同模式的默认超时：全量最长，资讯最短
MODE_TIMEOUTS: dict[str, int] = {
    "all": 7200,
    "quick": 3600,
    "navs": 3600,
    "risk": 3600,
    "detail": 3600,
    "holdings": 3600,
    "news": 600,
}
DEFAULT_TIMEOUT = 1800
# 启动宽限：子进程拉起并写回 PID 的时间
START_GRACE_SECONDS = 60
# 终止流程：先 SIGTERM 等一会儿，再 SIGKILL，再确认退出
TERMINATE_GRACE_SECONDS = 3.0
KILL_GRACE_SECONDS = 2.0
# 判断 PID 是否还是本任务进程时允许的启动时间误差
PID_START_TOLERANCE_SECONDS = 120
# 只有真正被执行的入口才算采集进程
SYNC_MODULES = frozenset({"scripts.sync_funds", "scripts.sync_news"})
SYNC_SCRIPTS = frozenset({"sync_funds.py", "sync_news.py"})
# 心跳超过该时长视为卡住（仅用于告警，不自动杀进程）
STUCK_HEARTBEAT_SECONDS = 600


def _read_result(job_id: int) -> dict[str, Any] | None:
    path = result_path(job_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _read_log_tail(log_file: str | None, max_lines: int = 25) -> str | None:
    if not log_file:
        return None
    path = LOG_DIR / log_file
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # tqdm 进度条用 \r 刷屏，过滤掉，只留真正的日志行
    lines = [
        line.strip() for line in re.split(r"[\r\n]+", raw) if line.strip() and "%|" not in line
    ]
    return "\n".join(lines[-max_lines:])[:2000] or None


def _ps_field(pid: int, field: str) -> str | None:
    """读取进程信息（POSIX）。取不到时返回 None，由调用方决定保守策略。"""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", f"{field}="],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = result.stdout.strip()
    return text or None


def _process_gone(pid: int) -> bool:
    """进程是否已经退出。

    只看 `os.kill(pid, 0)` 会把僵尸进程当成存活：子进程退出后要等父进程
    `wait()` 才消失。因此再看一眼 `ps` 的状态字段（Z 表示僵尸，已算退出）。
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    state = _ps_field(pid, "stat")
    if state is not None:
        return state.startswith("Z")
    # 精简镜像里可能没有 ps：若它是本进程的子进程，可以直接问内核是否已退出
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        return False
    return reaped == pid


def _pid_alive(pid: int) -> bool:
    return not _process_gone(pid)


def _pid_start_time(pid: int) -> datetime | None:
    text = _ps_field(pid, "lstart")
    if not text:
        return None
    for fmt in ("%a %b %d %H:%M:%S %Y", "%a %e %b %H:%M:%S %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _pid_tokens(command: str) -> list[str] | None:
    try:
        return shlex.split(command)
    except ValueError:
        return None


def _pid_job_id(tokens: list[str]) -> str | None:
    """从命令行 token 里**精确**取出 `--job-id` 的值。

    不能做子串包含：`--job-id 420` 里包含 "42"，任务 42 会认领任务 420 的进程，
    然后对着别人的采集进程发 SIGKILL。
    """
    for index, token in enumerate(tokens):
        if token == "--job-id" and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith("--job-id="):
            return token.split("=", 1)[1]
    return None


def _pid_entry(tokens: list[str]) -> str | None:
    """真正被执行的入口：`python -m <module>` 的模块名，或脚本路径。

    只看解释器之后的第一个位置参数。`--label scripts.sync_funds` 这类普通参数
    不算入口——否则任何人带一个同名参数，就能被当成采集进程去 SIGKILL。
    """
    args = tokens[1:] if tokens else []
    if not args:
        return None
    if args[0] == "-m":
        return args[1] if len(args) > 1 else None
    return args[0] if args[0].endswith(".py") else None


def _is_sync_entry(entry: str) -> bool:
    if entry in SYNC_MODULES:
        return True
    return entry.replace("\\", "/").rsplit("/", 1)[-1] in SYNC_SCRIPTS


def _pid_belongs(pid: int, job: SyncJob) -> bool:
    """确认这个 PID 还是本次任务启动的进程。

    判定要求**三条同时成立**：命令行是采集脚本、`--job-id` 与任务号完全相等、
    进程启动时间不晚于任务开始（PID 被复用时新进程会晚很多）。
    读不到命令行时不认领、不发信号——由 `_reconcile` 保留"运行中 + 告警"，
    交给运营排查，绝不"缺信息就默认放行"。
    """
    command = _ps_field(pid, "command")
    if command is None:
        logger.warning("任务 #%s 无法读取 PID %s 的命令行，保留运行中待人工核对", job.id, pid)
        return False
    tokens = _pid_tokens(command)
    if tokens is None:
        return False
    entry = _pid_entry(tokens)
    if entry is None or not _is_sync_entry(entry):
        return False
    job_id = _pid_job_id(tokens)
    if job_id is None or job_id != str(job.id):
        return False
    started = _pid_start_time(pid)
    # PID 被复用时，新进程的启动时间会明显晚于任务开始时间
    return not (
        started is not None
        and job.started_at is not None
        and started > job.started_at + timedelta(seconds=PID_START_TOLERANCE_SECONDS)
    )


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _load_failures(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [
        {"item": str(item.get("item", "")), "reason": str(item.get("reason", ""))}
        for item in data
        if isinstance(item, dict)
    ]


def _dump_failures(failures: object) -> str | None:
    if not isinstance(failures, list) or not failures:
        return None
    cleaned = [
        {"item": str(item.get("item", ""))[:60], "reason": str(item.get("reason", ""))[:160]}
        for item in failures
        if isinstance(item, dict)
    ]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


class SyncJobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------- 查询
    async def list_recent(self, limit: int = 20) -> list[SyncJobRead]:
        stmt = select(SyncJob).order_by(SyncJob.id.desc()).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        for job in rows:
            await self._reconcile(job)
        return [SyncJobRead.model_validate(job) for job in rows]

    async def get(self, job_id: int) -> SyncJobRead:
        job = await self.session.get(SyncJob, job_id)
        if job is None:
            raise NotFoundError("同步任务不存在")
        await self._reconcile(job)
        return SyncJobRead.model_validate(job)

    # ---------------------------------------------------------- 状态恢复
    async def _apply_progress(self, job: SyncJob) -> None:
        """把进度文件里的阶段与计数搬到任务行上（不改状态）。"""
        snapshot = read_progress(job.id)
        if not snapshot:
            return
        phase = snapshot.get("phase")
        if isinstance(phase, str):
            job.phase = phase
        for field in ("total", "succeeded", "failed", "skipped"):
            value = snapshot.get(field)
            if isinstance(value, int):
                setattr(job, field, value)
        job.failures = _dump_failures(snapshot.get("failures"))
        updated = _parse_dt(snapshot.get("updated_at"))
        job.heartbeat_at = updated or datetime.now()

    async def _reconcile(self, job: SyncJob, *, commit: bool = True) -> None:
        """把结果文件/进度/进程状态同步回数据库，处理 API 重启遗留的 running 任务。"""
        if job.status in TERMINAL_STATUSES:
            return

        result = _read_result(job.id)
        if result:
            job.status = str(result.get("status") or "success")
            job.finished_at = _parse_dt(result.get("finished_at")) or datetime.now()
            job.duration_ms = result.get("duration_ms")
            job.message = result.get("message")
            counts = result.get("counts")
            if isinstance(counts, dict):
                for field in ("total", "succeeded", "failed", "skipped"):
                    value = counts.get(field)
                    if isinstance(value, int):
                        setattr(job, field, value)
                job.failures = _dump_failures(counts.get("failures")) or job.failures
            job.log_tail = _read_log_tail(job.log_file)
            if commit:
                await self.session.commit()
            return

        await self._apply_progress(job)

        if job.pid and _pid_alive(job.pid):
            if self._exceeded_timeout(job):
                # API 重启后原 watcher 已经不存在，超时进程必须在这里收敛。
                # 注意：终止要等进程真的退出，否则 active 检查会放行下一轮任务，
                # 两批采集同时写库。
                exited = await self._terminate(job)
                if not exited:
                    job.status = "running"
                    job.message = "已超时但无法确认/终止子进程，请人工核对进程后再启动新任务"
                    job.heartbeat_at = datetime.now()
                    logger.error("任务 #%s 超时且子进程未退出，保持运行中", job.id)
                    if commit:
                        await self.session.commit()
                    return
                job.status = "timeout"
                job.finished_at = datetime.now()
                job.message = f"超过 {job.timeout_seconds} 秒未完成，已终止子进程"
                job.log_tail = _read_log_tail(job.log_file)
                if commit:
                    await self.session.commit()
                return
            job.status = "running"
            if job.cancel_requested:
                job.message = "已请求取消，等待当前条目处理完成"
            if commit:
                await self.session.commit()
            return  # 真在跑

        if job.status == "starting" and not job.pid:
            started = job.started_at or datetime.now()
            if (datetime.now() - started).total_seconds() < START_GRACE_SECONDS:
                if commit:
                    await self.session.commit()
                return  # 给刚创建的任务留出子进程启动与 PID 写回时间。

        job.finished_at = datetime.now()
        if job.cancel_requested or read_cancel_requested(job.id):
            job.status = "cancelled"
            job.message = "任务已取消"
        elif self._exceeded_timeout(job):
            job.status = "timeout"
            job.message = f"任务超过 {job.timeout_seconds} 秒未完成，已判定超时"
        else:
            job.status = "failed"
            job.message = "进程已退出且未写入结果（服务重启或异常终止）"
        job.log_tail = _read_log_tail(job.log_file)
        if commit:
            await self.session.commit()

    @staticmethod
    async def _wait_exit(pid: int, seconds: float) -> bool:
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            if _process_gone(pid):
                return True
            await asyncio.sleep(0.1)
        return _process_gone(pid)

    async def _terminate(self, job: SyncJob) -> bool:
        """SIGTERM → 有上限地等待 → SIGKILL → 确认退出。

        返回进程是否**确实退出**。只有确认退出后调用方才能把任务置为终态：
        否则下一轮任务会因为 active 检查放行而与本轮同时写库。
        """
        pid = job.pid
        if not pid or _process_gone(pid):
            return True
        if not _pid_belongs(pid, job):
            logger.warning("任务 #%s 无法确认 PID %s 的归属，跳过终止", job.id, pid)
            return False
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)
        if await self._wait_exit(pid, TERMINATE_GRACE_SECONDS):
            return True
        logger.warning("任务 #%s 未响应 SIGTERM，升级为 SIGKILL", job.id)
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)
        return await self._wait_exit(pid, KILL_GRACE_SECONDS)

    @staticmethod
    def _exceeded_timeout(job: SyncJob) -> bool:
        started = job.started_at or datetime.now()
        budget = job.timeout_seconds or DEFAULT_TIMEOUT
        return (datetime.now() - started).total_seconds() > budget

    # ---------------------------------------------------------- 触发
    async def start(
        self,
        payload: SyncTriggerRequest,
        username: str | None,
        *,
        allow_retry_of: int | None = None,
        schedule_id: int | None = None,
        scheduled_on: date | None = None,
    ) -> SyncJobRead:
        if payload.mode not in SYNC_MODES:
            raise ValidationError("不支持的同步模式")
        if payload.codes and not re.fullmatch(r"[0-9A-Za-z,\s]+", payload.codes):
            raise ValidationError("基金代码格式不正确")

        await self.session.execute(
            select(SyncJobMutex.id).where(SyncJobMutex.id == 1).with_for_update()
        )
        schedule = None
        if schedule_id is not None:
            schedule = (
                await self.session.execute(
                    select(SyncSchedule)
                    .where(SyncSchedule.id == schedule_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if schedule is None or not schedule.enabled or schedule.last_run_on == scheduled_on:
                raise ConflictError("定时任务已执行或已被停用")
        running = (
            await self.session.execute(
                select(SyncJob)
                .where(SyncJob.status.in_(ACTIVE_STATUSES))
                .order_by(SyncJob.id.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if running is not None:
            await self._reconcile(running, commit=False)
            if running.status in ACTIVE_STATUSES:
                raise ConflictError(
                    f"已有同步任务正在运行（#{running.id} · {running.mode}），请等待完成"
                )

        params = {
            k: v
            for k, v in {
                "limit": payload.limit,
                "codes": payload.codes,
                "force": payload.force or None,
            }.items()
            if v is not None
        }
        job = SyncJob(
            mode=payload.mode,
            params=json.dumps(params, ensure_ascii=False) if params else None,
            status="starting",
            phase=payload.mode,
            timeout_seconds=MODE_TIMEOUTS.get(payload.mode, DEFAULT_TIMEOUT),
            triggered_by=username,
            log_file="sync_job_pending.log",
        )
        self.session.add(job)
        await self.session.flush()
        if schedule is not None:
            schedule.last_run_on = scheduled_on
            schedule.last_job_id = job.id
        await self.session.commit()
        await self.session.refresh(job)

        job.log_file = f"sync_job_{job.id}.log"
        # 重试时沿用原任务的日志会串台，这里按新任务 ID 重新开一份
        await self.session.commit()
        clear_control_files(job.id)

        try:
            await self.spawn(job, payload)
            if job.status == "starting":
                job.status = "running"
                await self.session.commit()
            await self.session.refresh(job)
        except Exception as exc:
            await self.session.rollback()
            failed = await self.session.get(SyncJob, job.id)
            if failed is not None and failed.status in ACTIVE_STATUSES:
                failed.status = "failed"
                failed.finished_at = datetime.now()
                failed.message = f"启动失败：{exc!s}"[:500]
                failed.log_tail = _read_log_tail(failed.log_file)
                await self.session.commit()
                job = failed
            else:
                raise
        return SyncJobRead.model_validate(job)

    async def retry(self, job_id: int, username: str | None) -> SyncJobRead:
        """用一个**新任务**重跑历史任务的参数，历史记录保持不可变。"""
        job = await self.session.get(SyncJob, job_id)
        if job is None:
            raise NotFoundError("同步任务不存在")
        await self._reconcile(job)
        if job.status in ACTIVE_STATUSES:
            raise ConflictError("任务仍在运行，无需重试")
        payload = SyncTriggerRequest(mode=job.mode)
        if job.params:
            try:
                params = json.loads(job.params)
            except ValueError:
                params = {}
            if isinstance(params, dict):
                payload = SyncTriggerRequest(
                    mode=job.mode,
                    limit=params.get("limit"),
                    codes=params.get("codes"),
                    force=bool(params.get("force")),
                )
        return await self.start(payload, username, allow_retry_of=job.id)

    async def cancel(self, job_id: int) -> SyncJobRead:
        """请求取消：放标记文件让脚本在检查点退出；进程已不在则直接收敛。"""
        job = await self.session.get(SyncJob, job_id)
        if job is None:
            raise NotFoundError("同步任务不存在")
        await self._reconcile(job)
        if job.status in TERMINAL_STATUSES:
            raise ConflictError("任务已结束，无法取消")

        job.cancel_requested = True
        if job.pid and _pid_alive(job.pid):
            request_cancel(job.id)
            job.message = "已请求取消，等待当前条目处理完成"
        else:
            job.status = "cancelled"
            job.finished_at = datetime.now()
            job.message = "任务已取消"
        await self.session.commit()
        return SyncJobRead.model_validate(job)

    async def spawn(self, job: SyncJob, payload: SyncTriggerRequest) -> None:
        """启动采集子进程并挂一个 watcher；单独抽出便于测试 mock。"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        # 资讯同步是独立脚本：参数与结果文件格式保持一致，只换入口模块
        script = "scripts.sync_news" if job.mode == "news" else "scripts.sync_funds"
        args = [
            sys.executable,
            "-m",
            script,
            "--mode",
            job.mode,
            "--job-id",
            str(job.id),
        ]
        if payload.limit:
            args += ["--limit", str(payload.limit)]
        if payload.codes:
            args += ["--codes", payload.codes]
        if payload.force:
            args += ["--force"]

        log_path = LOG_DIR / (job.log_file or f"sync_job_{job.id}.log")
        with log_path.open("ab") as log_fh:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(API_DIR),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )
        job.pid = proc.pid
        job.status = "running"
        job.heartbeat_at = datetime.now()
        try:
            await self.session.commit()
            task = asyncio.create_task(
                self._watch(job.id, proc, job.timeout_seconds or DEFAULT_TIMEOUT)
            )
            _WATCHERS.add(task)
            task.add_done_callback(_WATCHERS.discard)
        except Exception:
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.terminate()
                await proc.wait()
            raise

    async def _watch(self, job_id: int, proc: asyncio.subprocess.Process, timeout: int) -> None:
        """子进程结束后用独立会话回填状态（请求会话此时已关闭）。"""
        timed_out = False
        try:
            returncode = await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            timed_out = True
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=15)
            except (TimeoutError, ProcessLookupError):
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()
            returncode = -1
        except Exception:
            returncode = -1

        result = _read_result(job_id)
        if timed_out:
            status = "timeout"
            message = f"超过 {timeout} 秒未完成，已终止子进程"
        elif result:
            status = str(result.get("status") or "success")
            message = str(result.get("message") or "同步完成")
        elif read_cancel_requested(job_id):
            status = "cancelled"
            message = "任务已取消"
        else:
            status = "success" if returncode == 0 else "failed"
            message = "同步完成" if returncode == 0 else f"采集进程异常退出（exit={returncode}）"

        async with async_session_factory() as session:
            job = await session.get(SyncJob, job_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return
            await self._apply_progress(job)
            job.status = status
            job.finished_at = _parse_dt((result or {}).get("finished_at")) or datetime.now()
            job.duration_ms = (result or {}).get("duration_ms")
            job.message = message[:500]
            job.log_tail = _read_log_tail(job.log_file)
            await session.commit()

    # ---------------------------------------------------------- 告警
    async def alerts(self, hours: int = 24) -> list[dict[str, Any]]:
        """运行告警：最近失败/超时任务 + 卡住的运行中任务。

        只做"发现问题"，通知渠道（邮件/IM）由部署侧接 `/admin/sync/alerts`。
        """
        since = datetime.now() - timedelta(hours=hours)
        rows = list(
            (
                await self.session.execute(
                    select(SyncJob)
                    .where(SyncJob.started_at >= since)
                    .order_by(SyncJob.id.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        alerts: list[dict[str, Any]] = []
        for job in rows:
            await self._reconcile(job)
            if job.status in ("failed", "timeout"):
                label = "超时" if job.status == "timeout" else "失败"
                alerts.append(
                    {
                        "level": "error",
                        "job_id": job.id,
                        "mode": job.mode,
                        "title": f"任务 #{job.id} {job.mode} {label}",
                        "detail": job.message or "无详细信息",
                        "at": (job.finished_at or job.started_at).isoformat(timespec="seconds"),
                    }
                )
            elif job.status in ACTIVE_STATUSES:
                heartbeat = job.heartbeat_at or job.started_at
                if (datetime.now() - heartbeat).total_seconds() > STUCK_HEARTBEAT_SECONDS:
                    minutes = STUCK_HEARTBEAT_SECONDS // 60
                    alerts.append(
                        {
                            "level": "warning",
                            "job_id": job.id,
                            "mode": job.mode,
                            "title": f"任务 #{job.id} 超过 {minutes} 分钟无进度",
                            "detail": job.message or "子进程仍在运行但未上报进度",
                            "at": heartbeat.isoformat(timespec="seconds"),
                        }
                    )
        return alerts[:20]


__all__ = [
    "ACTIVE_STATUSES",
    "LOG_DIR",
    "MODE_TIMEOUTS",
    "TERMINAL_STATUSES",
    "SyncJobService",
    "progress_path",
]
