"""AI 接口：内容助手对话 + 文章质检。

权限：登录即可使用（后台能力）。未配置模型密钥时返回 503，不影响其他接口。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from app.ai.agents.assistant import build_content_assistant
from app.ai.graphs.content_review import build_review_graph
from app.ai.llm import AINotConfiguredError
from app.ai.schemas import (
    AIStatus,
    ChatRequest,
    ChatResponse,
    ReviewRequest,
    ReviewResponse,
    ToolCallTrace,
)
from app.api.deps import CurrentUser, RequestIdDep
from app.core.config import settings
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/ai", tags=["后台 · AI"])


def _extract_tool_calls(messages: list[Any]) -> list[ToolCallTrace]:
    """从消息序列里提取工具调用轨迹，供前端展示"AI 查了什么"。"""
    traces: list[ToolCallTrace] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            traces.append(
                ToolCallTrace(name=call.get("name", "unknown"), args=call.get("args") or {})
            )
    return traces


def _extract_text(message: Any) -> str:
    """兼容纯文本与多模态片段两种返回。"""
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        ).strip()
    return str(content).strip()


@router.get("/status", summary="AI 能力状态", response_model=ApiResponse[AIStatus])
async def ai_status(_: CurrentUser) -> ApiResponse[AIStatus]:
    return ApiResponse.ok(
        AIStatus(
            enabled=settings.AI_ENABLED,
            ready=settings.ai_ready,
            model=settings.AI_MODEL if settings.AI_ENABLED else None,
            base_url=settings.OPENAI_BASE_URL if settings.AI_ENABLED else None,
        )
    )


@router.post("/chat", summary="内容运营助手对话", response_model=ApiResponse[ChatResponse])
async def chat(
    payload: ChatRequest, request_id: RequestIdDep, _: CurrentUser
) -> ApiResponse[ChatResponse]:
    if not settings.ai_ready:
        raise AINotConfiguredError()

    agent = build_content_assistant()
    thread_id = payload.thread_id or uuid.uuid4().hex

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": payload.message}]},
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.AI_MAX_ITERATIONS,
        },
    )

    messages: list[Any] = result.get("messages", [])
    reply = _extract_text(messages[-1]) if messages else ""

    return ApiResponse(
        data=ChatResponse(
            thread_id=thread_id,
            reply=reply,
            tool_calls=_extract_tool_calls(messages),
        ),
        request_id=request_id,
    )


@router.post(
    "/review",
    summary="文章质检（确定性规则 + 模型建议）",
    response_model=ApiResponse[ReviewResponse],
)
async def review(
    payload: ReviewRequest, request_id: RequestIdDep, _: CurrentUser
) -> ApiResponse[ReviewResponse]:
    if not settings.ai_ready:
        raise AINotConfiguredError()

    graph = build_review_graph()
    state = await graph.ainvoke(
        {"title": payload.title, "summary": payload.summary, "content": payload.content}
    )

    return ApiResponse(
        data=ReviewResponse(
            passed=bool(state.get("passed")),
            issues=list(state.get("issues") or []),
            suggestions=state.get("suggestions", ""),
        ),
        request_id=request_id,
    )
