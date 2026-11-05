# AI 能力（app/ai）

> 为后续接入大模型预留的能力层。当前提供两条路径：**智能体对话**（自主调用工具）和 **确定性工作流**（LangGraph 编排）。
> 设计底线：AI 可以"提议"，但不能"决定"业务红线。

## 1. 目录与职责

```
app/ai/
├── llm.py              模型工厂：唯一的 LLM 创建入口，换供应商只改这里
├── tools/              工具层：把 service 能力暴露给智能体（默认只读）
│   └── content.py      search_articles / get_article / content_overview
├── agents/             智能体：deepagents 组装（提示词 + 工具 + 会话记忆）
│   └── assistant.py    内容运营助手
├── graphs/             LangGraph 显式流程
│   └── content_review.py  质检：确定性规则 → 模型建议
├── prompts/            提示词（与代码一起版本化）
│   └── assistant.md
└── schemas.py          接口契约
```

依赖方向：`ai → services → repositories`。**工具层不直接查库**，否则软删除、状态过滤、权限规则会被绕过。

## 2. 两条路径怎么选

| | 智能体（deepagents） | 工作流（LangGraph） |
| --- | --- | --- |
| 适合 | 开放式问答、需要模型自己决定查什么 | 步骤固定、需要可预测结果 |
| 例子 | "最近有哪些关于产品的文章？" | 发布前质检、内容分级、批量改写 |
| 可控性 | 中（模型规划） | 高（节点顺序固定） |
| 能否离线测试 | 否（依赖模型） | 部分可以（确定性节点可单测） |
| 出错影响 | 答得不好 | 流程卡住（可加 interrupt 人工介入） |

**经验法则**：先问"如果模型瞎编，后果严重吗？"严重 → 用工作流 + 确定性节点；不严重 → 用智能体。

## 3. 配置

三步，任一缺失都不会让服务启动失败（接口返回 503 并说明缺什么）：

```bash
# 1. 打开开关
AI_ENABLED=true

# 2. 填密钥
OPENAI_API_KEY=sk-xxx

# 3. 选端点与模型（任意 OpenAI 兼容服务）
OPENAI_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
```

常见组合：

| 供应商 | OPENAI_BASE_URL | AI_MODEL 示例 |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 本地 vLLM | `http://127.0.0.1:8001/v1` | 按加载的模型名 |

验证：

```bash
curl http://127.0.0.1:8000/api/v1/ai/status -H "Authorization: Bearer <token>"
# {"code":0,"data":{"enabled":true,"ready":true,"model":"deepseek-chat",...}}
```

## 4. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/ai/status` | 是否启用、当前模型 |
| POST | `/api/v1/ai/chat` | 智能体对话，body：`{message, thread_id?}` |
| POST | `/api/v1/ai/review` | 文章质检，body：`{title, summary, content}` |

对话是有状态的：同一个 `thread_id` 会延续上下文（`InMemorySaver`）。生产环境应换成持久化 checkpointer。

响应里带 `tool_calls`，前端可以显示"AI 查了哪些数据"，避免黑箱感。

## 5. 加一个工具

场景：让助手能查"某个用户发了多少文章"。

```python
# app/ai/tools/content.py
@tool
async def user_article_count(username: str) -> str:
    """查询指定用户发布的文章数量。

    Args:
        username: 登录名。
    """
    async with async_session_factory() as session:
        # 走 service，不写 SQL
        count = await UserService(session).count_articles(username)
    return f"用户 {username} 共发布 {count} 篇文章。"

ALL_TOOLS = [search_articles, get_article, content_overview, user_article_count]
```

四件事必须做：

1. 用 `@tool` 装饰，**docstring 就是给模型的说明**，写清楚参数含义；
2. 在 `ALL_TOOLS` 登记，否则模型看不见；
3. 只读优先；写操作要加 `require_confirmation` 并在提示词里明确"需要用户确认"；
4. 工具内部自己开 session，用完释放。

## 6. 加一条工作流

场景：批量给文章打标签，流程固定。

```python
# app/ai/graphs/tagging.py
class TagState(TypedDict, total=False):
    title: str
    content: str
    tags: list[str]

def rule_tags(state: TagState) -> dict:      # 确定性：关键词匹配
    ...

async def llm_tags(state: TagState) -> dict:  # 模型：补充候选
    ...

def build_tag_graph():
    g = StateGraph(TagState)
    g.add_node("rule_tags", rule_tags)
    g.add_node("llm_tags", llm_tags)
    g.add_edge(START, "rule_tags")
    g.add_edge("rule_tags", "llm_tags")
    g.add_edge("llm_tags", END)
    return g.compile()
```

原则：**确定性节点在前，模型节点在后**；模型输出要能被代码校验（比如标签必须在白名单内）。

## 7. 安全与成本

| 风险 | 措施（已落地/建议） |
| --- | --- |
| 密钥泄漏 | 只放 `.env`，不入库；日志不打印 key |
| 提示词注入 | 工具只读；写操作需人工确认；系统提示词声明边界 |
| 数据外泄 | 送模型前脱敏（手机号、邮箱、身份证）；不要整表丢进上下文 |
| 成本失控 | `AI_MAX_ITERATIONS` 限制轮数；工具返回截断（如正文 3000 字）；记录 token 用量 |
| 模型不可用 | 接口返回 503，前端降级为普通表单，不阻塞主流程 |
| 幻觉 | 提示词要求"先查证再回答，查不到就说没有"；关键结论回到确定性代码 |

上线前建议补：请求级 token 统计、按用户限流、对话审计日志（谁的会话、调了哪些工具）。

## 8. 版本与升级注意

当前锁定：`langchain 1.4.x` / `langgraph 1.2.x` / `deepagents 0.7.x` / `langchain-openai 1.7.x`。

- LangChain 1.x 与 0.x 的 API 不兼容（`AgentExecutor` 已移除，改用 `create_agent`），**不要照搬 0.x 教程**。
- `deepagents` 仍处于 0.x，接口可能变。升级时先跑 `tests/test_ai.py`，再手动验证 `/ai/chat`。
- 升级命令：`uv add "deepagents>=0.8"`，并同步更新本文档的版本号。

## 9. 排障

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 503 `AI 能力未启用` | 没开 `AI_ENABLED` 或没填 key | 按第 3 节配置后重启 |
| 401 / 403 from provider | key 错误、余额不足、模型名不对 | 先用 curl 直连验证端点 |
| 回答里没有调用工具 | 提示词未要求、工具未登记 | 检查 `ALL_TOOLS` 与 `prompts/assistant.md` |
| 多轮对话失忆 | `thread_id` 每次变了 | 前端保存并复用同一个 `thread_id` |
| 超时 | 模型慢 / `AI_TIMEOUT` 太小 | 调大超时，或换更快的模型 |
