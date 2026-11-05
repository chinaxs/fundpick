"""AI 模块测试：未配置模型时不依赖外部服务，可离线跑。"""

from httpx import AsyncClient

from app.ai.graphs.content_review import check_rules


def test_check_rules_rejects_short_content() -> None:
    state = check_rules({"title": "短", "summary": "", "content": "太短"})
    assert state["passed"] is False
    assert len(state["issues"]) == 3


def test_check_rules_passes_valid_article() -> None:
    state = check_rules(
        {
            "title": "一套可维护的后端分层实践",
            "summary": "从路由到仓储，说明每层的职责边界。",
            "content": "正文内容需要足够长才能通过校验，" * 5,
        }
    )
    assert state["passed"] is True
    assert state["issues"] == []


async def test_ai_status_requires_login(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 401


async def test_ai_chat_without_key_returns_503(client: AsyncClient, monkeypatch) -> None:
    """未配置密钥时应返回 503 而不是 500，且给出可操作的提示。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_ENABLED", False)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    if login.status_code != 200:  # 未初始化数据的环境跳过
        return
    token = login.json()["data"]["access_token"]

    resp = await client.post(
        "/api/v1/ai/chat",
        json={"message": "现在有多少篇文章？"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == 50300


async def test_review_graph_runs_with_fake_model(monkeypatch) -> None:
    """用假模型跑通整条图：规则节点 + 模型节点 + 状态传递。

    这样 CI 里无需真实 API Key 也能验证编排逻辑没写错。
    """
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    import app.ai.graphs.content_review as review_module

    monkeypatch.setattr(
        review_module,
        "get_chat_model",
        lambda **_: FakeListChatModel(responses=["建议：标题可以更具体"]),
    )

    graph = review_module.build_review_graph()
    state = await graph.ainvoke(
        {
            "title": "一套可维护的后端分层实践",
            "summary": "从路由到仓储，说明每层的职责边界。",
            "content": "正文内容需要足够长才能通过校验，" * 5,
        }
    )

    assert state["passed"] is True
    assert state["issues"] == []
    assert "建议" in state["suggestions"]
