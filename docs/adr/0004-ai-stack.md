# 0004 · AI 采用 LangChain + LangGraph + deepagents 分层

- **状态**：已采纳
- **日期**：2026-11-05

## 背景

项目后期要接入 AI（内容助手、质检、可能的 RAG）。需要现在就把"放哪儿、怎么放"定下来，避免以后在业务代码里散落 `openai.chat.completions.create`。

约束：团队 Python 栈、已有 FastAPI 服务、希望换模型供应商时改动最小、不希望 AI 阻塞主业务。

## 决策

在 `services/api/app/ai/` 建立独立 AI 层，三个组件各司其职：

| 组件 | 用途 |
| --- | --- |
| **LangChain**（`langchain-openai`） | 模型接入与消息抽象，统一不同供应商的调用方式 |
| **LangGraph** | 需要固定步骤、可中断、可测试的流程（如质检） |
| **deepagents** | 需要自主规划、多步调用工具的开放任务（如运营助手） |

## 理由

1. **分层而非二选一**：确定性流程用 LangGraph（可单测、可加人工确认），开放任务用 deepagents（少写编排代码）。两者都基于 LangGraph，模型与工具定义可共用。
2. **模型可替换**：`ChatOpenAI` 支持任意 OpenAI 兼容端点，切换 DeepSeek / 通义 / 本地 vLLM 只改 `.env`。
3. **不侵入业务**：工具层只调 service，业务规则仍是确定性代码；AI 挂了不影响主流程（返回 503）。
4. **先有骨架再有功能**：避免后期把 prompt 和调用逻辑撒进 endpoints。

## 备选方案

| 方案 | 为什么不选 |
| --- | --- |
| 直接用 openai SDK | 换供应商要改调用代码；没有工具/流程抽象，后期会重复造轮子 |
| 只用 LangChain AgentExecutor | 1.x 已移除该 API；且缺乏"固定流程"的可控性 |
| 只用 deepagents | 简单确定性流程也用智能体，成本高且不可预测 |
| 自研编排 | 重复造轮子，LangGraph 已提供状态、检查点、中断、流式 |
| Dify / Coze 等平台 | 适合快速验证，但与代码库割裂，复杂业务难落地 |

## 后果

- 好处：AI 能力有明确归口；工具可复用业务逻辑；供应商可切换。
- 代价：引入约 30 个传递依赖；`deepagents` 仍是 0.x，接口可能变动（已锁定版本并写了升级注意事项）。
- 重新评估触发条件：
  - 若只需"单轮文本生成"，可退化为直接调 `langchain-openai`，移除 graph/agent 层；
  - 若 `deepagents` 停止维护，可迁移到 `langgraph` 的 Supervisor 模式（工具与提示词可复用）。
