"""关注相关模型。"""

from pydantic import BaseModel, Field


class FavoriteToggleRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10, description="基金代码")


class FavoriteToggleResponse(BaseModel):
    code: str
    favorited: bool
