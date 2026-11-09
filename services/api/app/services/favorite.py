"""基金关注业务逻辑。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.favorite import FavoriteRepository
from app.repositories.fund import FundRepository
from app.schemas.common import PageResult
from app.schemas.fund import FundListItem
from app.services.fund import to_list_item


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.favorites = FavoriteRepository(session)
        self.funds = FundRepository(session)

    async def codes(self, user_id: int) -> list[str]:
        return await self.favorites.codes(user_id)

    async def page(
        self, user_id: int, page: int, page_size: int, period: str = "1y"
    ) -> PageResult[FundListItem]:
        rows, total = await self.favorites.paginate(user_id, page, page_size, period)
        return PageResult(
            items=[to_list_item(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def add(self, user_id: int, code: str) -> bool:
        """关注。已关注时幂等返回，不报错。"""
        fund = await self.funds.get_by_code(code)
        if fund is None:
            raise NotFoundError("基金不存在")
        await self.favorites.add(user_id, fund.id)
        await self.session.commit()
        return True

    async def remove(self, user_id: int, code: str) -> bool:
        fund = await self.funds.get_by_code(code)
        if fund is None:
            raise NotFoundError("基金不存在")
        await self.favorites.remove(user_id, fund.id)
        await self.session.commit()
        return False
