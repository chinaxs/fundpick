"""会员反馈工单。

门户侧只能看到自己提交的工单；后台按状态/分类处理并公开回复。
回复对会员可见，因此措辞要避免内部信息（后台备注不落库）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.support import Feedback, FeedbackStatus
from app.models.user import User
from app.schemas.support import FeedbackCreate, FeedbackListItem, FeedbackRead, FeedbackUpdate


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: int, payload: FeedbackCreate) -> FeedbackRead:
        feedback = Feedback(
            user_id=user_id,
            category=payload.category,
            title=payload.title.strip(),
            content=payload.content.strip(),
            contact=payload.contact,
            page_url=payload.page_url,
        )
        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)
        return FeedbackRead.model_validate(feedback)

    async def list_mine(self, user_id: int, limit: int = 20) -> list[FeedbackRead]:
        rows = (
            await self.session.execute(
                select(Feedback)
                .where(Feedback.user_id == user_id)
                .order_by(Feedback.id.desc())
                .limit(limit)
            )
        ).scalars()
        return [FeedbackRead.model_validate(row) for row in rows]

    async def list_admin(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[FeedbackListItem], int]:
        stmt = select(Feedback, User).join(User, User.id == Feedback.user_id, isouter=True)
        count_stmt = select(func.count()).select_from(Feedback)
        conditions = []
        if status:
            conditions.append(Feedback.status == status)
        if category:
            conditions.append(Feedback.category == category)
        if keyword:
            like = f"%{keyword.strip()}%"
            conditions.append(or_(Feedback.title.like(like), Feedback.content.like(like)))
        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)
        rows = (
            await self.session.execute(
                stmt.order_by(Feedback.id.desc()).limit(page_size).offset((page - 1) * page_size)
            )
        ).all()
        items = [
            FeedbackListItem(
                **FeedbackRead.model_validate(feedback).model_dump(),
                username=user.username if user else None,
                email=user.email if user else None,
            )
            for feedback, user in rows
        ]
        return items, total

    async def update(self, feedback_id: int, payload: FeedbackUpdate, handler: str) -> FeedbackRead:
        feedback = await self.session.get(Feedback, feedback_id)
        if feedback is None:
            raise NotFoundError("反馈不存在")
        if payload.status is not None:
            feedback.status = payload.status
            feedback.handled_by = handler
            feedback.handled_at = datetime.now()
        if payload.reply is not None:
            feedback.reply = payload.reply.strip() or None
            feedback.handled_by = handler
            feedback.handled_at = datetime.now()
        await self.session.commit()
        await self.session.refresh(feedback)
        return FeedbackRead.model_validate(feedback)

    async def open_count(self, user_id: int) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Feedback)
                    .where(
                        Feedback.user_id == user_id,
                        Feedback.status.in_(
                            [FeedbackStatus.OPEN.value, FeedbackStatus.PROCESSING.value]
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )
