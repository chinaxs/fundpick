"""数据同步任务模型。

后台点击「立即同步」或调度触发时创建一条记录；采集脚本在独立子进程执行，
进程结束时写结果文件，运行期间写进度文件，API 侧据此回填状态
（见 services/sync_job.py）。进度走文件而不是数据库，是为了让采集脚本
保持纯 CLI：脚本不依赖 API 进程，也不会在采集过程中占用业务连接池。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = {"comment": "数据同步任务记录"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="同步模式")
    params: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="参数 JSON")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="starting",
        index=True,
        comment="starting/running/partial_success/success/failed/cancelled/timeout",
    )
    # ---- 进度（由采集脚本的进度文件回填）----
    phase: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="当前阶段，如 risk / navs"
    )
    total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="本阶段目标数"
    )
    succeeded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="本阶段成功数"
    )
    failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="本阶段失败数"
    )
    skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="本阶段跳过数"
    )
    failures: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败明细 JSON：[{item, reason}]"
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次进度心跳"
    )
    # ---- 控制 ----
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="已请求取消，子进程在下个检查点退出",
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1800, server_default="1800", comment="超时秒数"
    )
    triggered_by: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="触发人（后台账号 / scheduler）"
    )
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="子进程 PID")
    log_file: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="日志文件相对名"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="开始时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="结束时间"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="耗时（毫秒）")
    message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="结果或错误信息"
    )
    log_tail: Mapped[str | None] = mapped_column(Text, nullable=True, comment="日志末尾摘录")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SyncJob {self.id} {self.mode} {self.status}>"


class SyncJobMutex(Base):
    """单行数据库互斥锁，串行化跨 API worker 的任务启动。"""

    __tablename__ = "sync_job_mutex"
    __table_args__ = {"comment": "数据同步任务启动互斥锁"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class SyncSchedule(TimestampMixin, Base):
    """每日定时采集配置。

    只表达"每周几的几点跑哪个模式"，不引入 cron 表达式：
    基金数据是 T+1 日频，分钟级精度没有意义，简单规则更容易核对。
    """

    __tablename__ = "sync_schedules"
    __table_args__ = {"comment": "数据同步定时配置"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, comment="同步模式")
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=18, comment="小时 0-23")
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="分钟 0-59")
    weekdays: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1,2,3,4,5",
        server_default="1,2,3,4,5",
        comment="ISO 星期（1=周一），逗号分隔；空表示每天",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", comment="是否启用"
    )
    last_run_on: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="最近一次触发日期（防同日重复）"
    )
    last_job_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="最近一次产生的任务"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SyncSchedule {self.id} {self.mode} {self.hour:02d}:{self.minute:02d}>"
