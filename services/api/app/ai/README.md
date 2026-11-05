# AI 能力（ai）

为大模型能力预留的独立层：模型工厂 + 工具 + 智能体 + 工作流。完整说明见 [docs/ai.md](../../../../docs/ai.md)。

## 边界
- 负责：模型调用、工具定义、提示词、图流程编排。
- 不负责：业务规则（在 service）、数据访问（通过 service 间接访问）、鉴权（在 deps）。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `llm.py` | `get_chat_model()` 唯一入口；未配置时抛 `AINotConfiguredError`(503) |
| `tools/content.py` | `search_articles` / `get_article` / `content_overview`（只读） |
| `agents/assistant.py` | deepagents 内容助手（单例 + 内存会话） |
| `graphs/content_review.py` | LangGraph 质检：规则校验 → 模型建议 |
| `prompts/assistant.md` | 系统提示词（与代码一起版本化） |
| `schemas.py` | 接口契约 |

## 扩展方式
- 加工具：写 `@tool` 函数 → 在 `ALL_TOOLS` 登记 → 更新提示词（见 docs/ai.md 第 5 节）。
- 加流程：`graphs/` 新建 StateGraph，确定性节点在前、模型节点在后。
- 换模型：只改 `.env`（`OPENAI_BASE_URL` / `AI_MODEL`），不改代码。

## 依赖
上游：`services`、`core`、`db` ｜ 下游：`api.v1.admin.ai`
