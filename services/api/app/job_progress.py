"""采集任务的进度与取消协议。

采集脚本在独立子进程运行，和 API 之间只用**文件**通信：

```
logs/sync_job_<id>.progress.json   脚本写，API 读：阶段、计数、失败明细
logs/sync_job_<id>.cancel           API 写，脚本读：请求取消
logs/sync_job_<id>.result.json     脚本写，API 读：最终状态
```

为什么不用数据库或消息队列：脚本要在没有 API 的情况下也能独立跑（CLI），
进度是"尽力而为"的可观测信息，丢一帧不影响业务正确性；而写库会在采集
过程中占用连接池，还会把脚本和 API 的生命周期绑死。

取消采用「检查点」语义：API 只放标记文件，脚本在处理完当前基金后退出并
把状态写成 cancelled，避免中途硬杀进程导致事务只提交了一半。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
MAX_FAILURES = 20


class SyncCancelled(RuntimeError):
    """脚本在检查点发现取消标记，正常终止本轮采集。"""


def progress_path(job_id: int) -> Path:
    return LOG_DIR / f"sync_job_{job_id}.progress.json"


def cancel_path(job_id: int) -> Path:
    return LOG_DIR / f"sync_job_{job_id}.cancel"


def result_path(job_id: int) -> Path:
    return LOG_DIR / f"sync_job_{job_id}.result.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """先写临时文件再替换，避免 API 读到写了一半的 JSON。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:  # 磁盘异常不应影响采集本身
        tmp.unlink(missing_ok=True)


def read_progress(job_id: int) -> dict[str, Any] | None:
    path = progress_path(job_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_cancel_requested(job_id: int) -> bool:
    return cancel_path(job_id).exists()


def request_cancel(job_id: int) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cancel_path(job_id).touch()


def clear_control_files(job_id: int) -> None:
    """重试前清掉上一次的取消标记与进度，避免新任务一启动就退出。"""
    for path in (cancel_path(job_id), progress_path(job_id)):
        path.unlink(missing_ok=True)


class JobProgress:
    """采集脚本侧上报器。

    参数：
        job_id: 后台任务 ID；CLI 直接运行时为 None，此时所有方法都是空操作。
        interval: 最小写入间隔（秒），避免逐条基金写盘。
    """

    def __init__(self, job_id: int | None, interval: float = 1.0) -> None:
        self.job_id = job_id
        self.interval = interval
        self.phase: str | None = None
        self.total = 0
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0
        self.failures: list[dict[str, str]] = []
        self._last_flush = 0.0

    @property
    def enabled(self) -> bool:
        return self.job_id is not None

    def begin(self, phase: str, total: int | None = None) -> None:
        """进入新阶段。

        计数**跨阶段累加**：任务详情里的「目标 / 成功 / 失败 / 跳过」是整轮采集的
        合计，`phase` 只表示当前正在跑哪一步。这样 `all` 这类多阶段模式也能
        给出一个可核对的总量，而不是每次归零让人误以为进度倒退。
        """
        self.phase = phase
        self.total += total or 0
        self.flush(force=True)

    def advance(self, *, ok: int = 0, failed: int = 0, skipped: int = 0) -> None:
        self.succeeded += ok
        self.failed += failed
        self.skipped += skipped
        self.flush()

    def fail(self, item: str, reason: str) -> None:
        """记录一条失败明细（最多保留 20 条，够定位问题即可）。"""
        self.failed += 1
        if len(self.failures) < MAX_FAILURES:
            self.failures.append({"item": item[:60], "reason": reason[:160]})
        self.flush()

    def checkpoint(self) -> None:
        """在处理每只基金的间隙调用；发现取消标记就抛出 SyncCancelled。"""
        if self.job_id is not None and read_cancel_requested(self.job_id):
            self.flush(force=True)
            raise SyncCancelled

    def flush(self, *, force: bool = False) -> None:
        if self.job_id is None:
            return
        now = time.monotonic()
        if not force and now - self._last_flush < self.interval:
            return
        self._last_flush = now
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write(
            progress_path(self.job_id),
            {
                "phase": self.phase,
                "total": self.total,
                "succeeded": self.succeeded,
                "failed": self.failed,
                "skipped": self.skipped,
                "failures": self.failures,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )


def summarize_failures(failures: list[dict[str, str]]) -> str | None:
    """把失败明细压成一句话，用于列表页的结果列。"""
    if not failures:
        return None
    first = failures[0]
    head = f"{first.get('item', '')}：{first.get('reason', '')}"
    if len(failures) == 1:
        return head
    return f"{head}（另 {len(failures) - 1} 条）"


__all__ = [
    "LOG_DIR",
    "JobProgress",
    "SyncCancelled",
    "clear_control_files",
    "progress_path",
    "read_cancel_requested",
    "read_progress",
    "request_cancel",
    "result_path",
    "summarize_failures",
]
