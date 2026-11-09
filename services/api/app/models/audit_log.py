"""操作审计日志。

`user_id` 与 `username` 都存，且**不设外键**：
审计记录要独立留存，用户被删除后仍能回答"当时是谁做的"。
username 是写入时的快照，避免用户改名后历史记录跟着变。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """后台写操作的审计轨迹。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_resource_created", "resource", "created_at"),
        {"comment": "操作审计日志"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True, comment="操作人 ID（不设外键）"
    )
    username: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="操作人用户名快照"
    )
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="动作：create/update/delete/login/other"
    )
    resource: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="资源：users/articles/funds/auth"
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="资源 ID（路径中提取）"
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False, comment="HTTP 方法")
    path: Mapped[str] = mapped_column(String(255), nullable=False, comment="请求路径")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="响应状态码")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="来源 IP")
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="处理耗时（毫秒）"
    )
    detail: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="查询参数摘要（不含敏感值）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="操作时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.username} {self.method} {self.path} {self.status_code}>"
