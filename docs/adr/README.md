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
