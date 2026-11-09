"""AI 工具的输入输出契约。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000, description="用户消息")
    thread_id: str | None = Field(
        default=None, description="会话 ID；同一 ID 可延续上下文，留空则新建"
    )


class ToolCallTrace(BaseModel):
    """一次工具调用记录，便于前端展示与排查。"""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    tool_calls: list[ToolCallTrace] = Field(default_factory=list, description="本次用到的工具")


class ReviewRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = None
    content: str = ""


class ReviewResponse(BaseModel):
    passed: bool = Field(description="是否通过确定性规则校验")
    issues: list[str] = Field(default_factory=list, description="规则校验发现的问题")
    suggestions: str = Field(default="", description="模型给出的写作建议（不参与放行判断）")


class AIStatus(BaseModel):
    """AI 能力状态：便于前端判断是否展示入口。"""

    enabled: bool
    ready: bool
    model: str | None = None
    base_url: str | None = None
