"""内容运营助手（deepagents）。

deepagents 负责"自主规划 + 调用工具"的部分；确定性的业务规则仍然留在 service 层。
两者的分工：模型决定"用什么工具、怎么组织回答"，代码决定"数据是什么、能不能改"。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from app.ai.llm import get_chat_model
from app.ai.tools import ALL_TOOLS

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "assistant.md"

# 会话状态存储：开发期用内存即可；生产应换成持久化 checkpointer（如 sqlite / postgres）
_CHECKPOINTER = InMemorySaver()


def load_system_prompt() -> str:
    """读取系统提示词（与代码一起版本化，不写在业务代码里）。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def build_content_assistant() -> Any:
    """构建助手实例。

    单例原因：checkpointer 持有会话历史，多轮对话必须复用同一个图实例。
    修改模型或工具后需重启服务（开发期可接受；生产可用配置中心 + 重建）。
    """
    return create_deep_agent(
        model=get_chat_model(),
        tools=list(ALL_TOOLS),
        system_prompt=load_system_prompt(),
        checkpointer=_CHECKPOINTER,
        name="content-assistant",
    )
