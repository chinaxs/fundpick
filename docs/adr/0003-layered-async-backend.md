# 0003 · 后端四层分层 + 全异步 SQLAlchemy

- **状态**：已采纳
- **日期**：2026-11-05

## 背景

FastAPI 项目最常见的腐化路径是：路由里直接写 SQL、业务逻辑散落在各 handler、事务边界不清。
项目预期长期迭代并接入 AI 能力（工具需要复用业务逻辑），必须先把边界定死。

## 决策

采用 `endpoints → services → repositories → models` 四层，全链路异步（`asyncmy` + `AsyncSession`），
事务提交只在 service 层，异常统一用 `AppException` 家族。

## 理由

1. **可复用**：AI 工具、定时任务、CLI 都能调用 service，而不必复制路由逻辑。
2. **可测试**：service 不依赖 HTTP，纯 pytest 即可覆盖。
3. **事务清晰**：一个业务动作一次 commit，避免"路由提交一半、仓储又提交一次"。
4. **异步是 FastAPI 的默认优势**：I/O 密集场景下并发能力显著优于同步线程池。

## 备选方案

| 方案 | 为什么不选 |
| --- | --- |
| 路由直连 ORM（简单项目常见） | 业务一复杂就重复代码，AI 工具无法复用 |
| 同步 SQLAlchemy + 线程池 | 需要额外的 `to_thread` 包装，且易阻塞事件循环 |
| Django ORM | 与 FastAPI 生态割裂，异步支持较弱 |

## 后果

- 好处：新增模块有固定路径可循；AI/批处理可复用 service。
- 代价：简单 CRUD 也要写 3 个文件（可用 `BaseRepository` 减少样板）；异步下需注意对象过期问题（`expire_on_commit=False` + 必要时 `refresh`）。
- 重新评估触发条件：如果出现大量跨表聚合报表，可单独引入只读查询层，不破坏现有分层。
