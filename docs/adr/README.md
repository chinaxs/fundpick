# ADR 索引

> 记录"为什么这样做"的短文档。当有人问"为什么不换个方案"时，先看这里。
> 新增决策：复制 `template.md`，编号递增，写完在下面登记。

| 编号 | 决策 | 状态 | 日期 |
| --- | --- | --- | --- |
| [0001](0001-monorepo-pnpm.md) | 用 pnpm workspace 组织单仓多包 | 已采纳 | 2026-11-05 |
| [0002](0002-nuxt-for-portal.md) | 门户用 Nuxt（SSR），后台用 Vue SPA | 已采纳 | 2026-11-05 |
| [0003](0003-layered-async-backend.md) | 后端分四层 + 全异步 SQLAlchemy | 已采纳 | 2026-11-05 |
| [0004](0004-ai-stack.md) | AI 采用 LangChain + LangGraph + deepagents 分层 | 已采纳 | 2026-11-05 |
| [0005](0005-package-boundaries.md) | shared 包不依赖任何框架 | 已采纳 | 2026-11-05 |
| [0006](0006-fund-data-source.md) | 第一期基金数据源用 AkShare（临时，商用前必换） | 已采纳 | 2026-11-06 |
| [0007](0007-same-origin-proxy.md) | 门户浏览器请求走同源反代，不依赖 CORS 白名单 | 已采纳 | 2026-11-06 |
| [0008](0008-api-grouping-by-consumer.md) | 接口按调用方分组：portal / admin / common | 已采纳 | 2026-11-06 |
| [0009](0009-portal-member-isolation.md) | 门户会员与后台账号双重隔离（is_staff + StaffUser） | 被 0010 取代 | 2026-11-06 |
| [0010](0010-split-staff-users-table.md) | 后台员工拆分到独立的 staff_users 表（拆表 + 令牌 scope） | 已采纳 | 2026-11-06 |
| [0011](0011-confirmed-simulated-trade-ledger.md) | 已确认模拟交易流水、预览确认与移动平均成本 | 已采纳 | 2026-11-08 |
| [0012](0012-record-real-platform-receipts.md) | 真实平台回执优先，分开申请时间、净值日和确认日 | 已采纳 | 2026-11-08 |
| [0013](0013-automatic-trade-calculation.md) | 金额时间自动记账、公开费率与估算来源 | 已采纳 | 2026-11-08 |
| [0014](0014-trade-record-lifecycle-and-history.md) | 自动等待入账、统一记录筛选分页与作废删除 | 已采纳 | 2026-11-08 |
| [0015](0015-in-process-sync-scheduler.md) | 采集定时用进程内轻量调度器 + 数据表配置 | 已采纳 | 2026-11-08 |
| [0016](0016-ledger-replay-as-source-of-truth.md) | 持仓以统一账本重放为准，流水快照只作历史展示 | 已采纳 | 2026-11-08 |
| [0017](0017-company-action-platform-and-idempotency.md) | 公司行为按平台归属，写入串行化并支持幂等键 | 已采纳 | 2026-11-08 |
