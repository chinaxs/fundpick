"""基金关注表。

取消关注用**硬删除**：关注是瞬时动作，保留软删记录会和唯一约束
（user_id + fund_id）冲突，导致"取消后再关注"插入失败。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FundFavorite(Base):
    """用户关注的基金。"""

    __tablename__ = "fund_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "fund_id", name="uq_favorite_user_fund"),
        Index("ix_favorite_user_created", "user_id", "created_at"),
        {"comment": "基金关注表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="用户"
    )
    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funds.id"), nullable=False, index=True, comment="基金"
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="关注时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundFavorite user={self.user_id} fund={self.fund_id}>"
