"""模型工厂：全项目唯一的 LLM 创建入口。

为什么集中在这里：
- 换供应商（OpenAI / DeepSeek / 通义 / 自建 vLLM）只改这一个文件；
- 超时、重试、温度等策略统一，避免各处参数不一致；
- 未配置密钥时抛业务异常，而不是在 import 阶段让服务起不来。
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.exceptions import AppException


class AINotConfiguredError(AppException):
    """AI 能力未启用。返回 503 而不是 500：这是配置缺失，不是程序缺陷。"""

    status_code = 503
    code = 50300
    message = "AI 能力未启用：请在 .env 中设置 AI_ENABLED=true 与 OPENAI_API_KEY"


def get_chat_model(*, temperature: float | None = None) -> BaseChatModel:
    """创建对话模型实例。

    任何 OpenAI 兼容端点都可直接使用（DeepSeek、Moonshot、通义千问等），
    只需配置 OPENAI_BASE_URL 与 AI_MODEL。
    """
    if not settings.ai_ready:
        raise AINotConfiguredError()

    return ChatOpenAI(
        model=settings.AI_MODEL,
        api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
        base_url=settings.OPENAI_BASE_URL,
        temperature=settings.AI_TEMPERATURE if temperature is None else temperature,
        max_tokens=settings.AI_MAX_TOKENS,
        timeout=settings.AI_TIMEOUT,
        max_retries=2,
    )
