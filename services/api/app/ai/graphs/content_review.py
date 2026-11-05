"""内容质检工作流（LangGraph）。

为什么这里用 LangGraph 而不是让 agent 自由发挥：
- 发布前的硬性校验（字数、必填、摘要长度）必须是确定性代码，模型无权决定"是否放行"；
- 图结构让每个节点可单独测试、可替换、可插入人工确认（interrupt）；
- 未来加节点（敏感词、SEO 评分、配图检查）只需加边，不改调用方。

节点职责：
  check_rules          纯函数校验 → 给出 issues 与 passed
  suggest_improvements 模型给建议   → 只影响 suggestions，不影响 passed
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.llm import get_chat_model


class ReviewState(TypedDict, total=False):
    title: str
    summary: str
    content: str
    issues: list[str]
    passed: bool
    suggestions: str


def check_rules(state: ReviewState) -> dict[str, Any]:
    """确定性校验：不调用模型，结果可预测、可单测。"""
    issues: list[str] = []
    title = (state.get("title") or "").strip()
    summary = (state.get("summary") or "").strip()
    content = (state.get("content") or "").strip()

    if len(title) < 5:
        issues.append("标题过短（少于 5 个字），不利于检索与点击")
    if not summary:
        issues.append("缺少摘要，门户列表页会没有导语")
    elif len(summary) > 500:
        issues.append("摘要超过 500 字，列表页会被截断")
    if len(content) < 50:
        issues.append("正文过短（少于 50 字），建议补充细节")

    return {"issues": issues, "passed": not issues}


async def suggest_improvements(state: ReviewState) -> dict[str, Any]:
    """模型建议：只产出意见，不参与放行判断。"""
    model = get_chat_model(temperature=0.3)
    prompt = (
        "你是资深内容编辑。请用不超过 3 条建议，指出下面文章在标题吸引力、"
        "摘要信息量和正文结构上的改进点。只给建议，不要重写全文。\n\n"
        f"标题：{state.get('title', '')}\n"
        f"摘要：{state.get('summary') or '（无）'}\n"
        f"正文：{(state.get('content') or '')[:2000]}"
    )
    response = await model.ainvoke(prompt)

    text = response.content
    if isinstance(text, list):  # 多模态模型可能返回片段数组
        text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in text
        )
    return {"suggestions": str(text).strip()}


def build_review_graph() -> Any:
    """编译质检流程：START → 规则校验 → 模型建议 → END。"""
    graph = StateGraph(ReviewState)
    graph.add_node("check_rules", check_rules)
    graph.add_node("suggest_improvements", suggest_improvements)
    graph.add_edge(START, "check_rules")
    graph.add_edge("check_rules", "suggest_improvements")
    graph.add_edge("suggest_improvements", END)
    return graph.compile()
