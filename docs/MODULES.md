# 模块地图（MODULES）

> 新增功能前先在这里定位：**这件事该落在哪个模块？** 找不到归属，说明模块划分有问题，先讨论再写。
> 每个模块目录下都有 `README.md`，说明职责边界与扩展方式。

## 全景

```
┌───────────────────────────── 前端 ─────────────────────────────┐
│  apps/admin（Vue SPA）           apps/portal（Nuxt SSR）        │
│  views → api → stores            pages → composables            │
│          ↘        ↙                     ↓                      │
│         packages/shared（类型 · 常量 · 纯函数）                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP /api/v1
┌──────────────────────────────▼──────────────────────────────────┐
│                        services/api（FastAPI）                   │
│  api/v1 → services → repositories → models                      │
│                     ↑                                           │
│                   ai/（tools 调 services，不直接碰库）            │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
                         MySQL (test_study)
```

## 后端模块

| 模块 | 路径 | 一句话职责 | 不该做什么 | 文档 |
| --- | --- | --- | --- | --- |
| 路由层 | `app/api/v1/{portal,admin,common}/` | 解析参数、鉴权、调用 service、包装响应 | 写 SQL、写业务分支 | [README](../services/api/app/api/README.md) |
| 依赖注入 | `app/api/deps.py` | 会话、当前用户、权限、request_id | 放业务逻辑 | 同上 |
| 业务层 | `app/services/` | 业务规则、事务边界、跨仓储编排 | 依赖 HTTP 概念 | [README](../services/api/app/services/README.md) |
| 仓储层 | `app/repositories/` | 查询构造、CRUD、软删除过滤 | 抛业务异常、写规则 | [README](../services/api/app/repositories/README.md) |
| 模型层 | `app/models/` | 表结构、索引、字段注释 | 写业务方法 | [README](../services/api/app/models/README.md) |
| 契约层 | `app/schemas/` | 请求/响应模型、校验规则 | 查库 | [README](../services/api/app/schemas/README.md) |
| 基础设施 | `app/core/` | 配置、安全、日志、异常 | 依赖业务模块 | [README](../services/api/app/core/README.md) |
| 数据连接 | `app/db/` | 引擎、会话工厂、ORM 基类 | 写具体业务查询 | [README](../services/api/app/db/README.md) |
| 通用工具 | `app/utils/` | 无副作用的纯函数 | 变成垃圾桶 | — |
| 数据源 | `app/datasources/` | 抽象外部数据接入，隔离供应商差异 | 把业务规则写进采集层 | [README](../services/api/app/datasources/README.md) |
| 市场行情 | `app/market_indices.py` + `services/market_index.py` | 核心指数清单、交易时段判定、短缓存与单飞降级、SSE 广播（`QuoteStream`）、当日分时与日 K | 写成通用行情代理；接受前端随意传代码；让每条 SSE 连接各自拉上游 | — |
| 资讯同步 | `app/news_sources.py` + `scripts/sync_news.py` | 快讯采集、相关性过滤、跨源去重、分类；写入文章草稿 | 全文转载；自动发布未经审核的内容 |
| 采集任务中心 | `app/job_progress.py` + `services/sync_job.py` + `services/sync_schedule.py` | 阶段/计数/失败明细/取消/超时/重试与定时调度；多 worker 靠数据库互斥 | 在 API 进程里直接跑采集；为一天一次的任务引入消息队列 |
| 会员支持 | `services/feedback.py` + `services/password_reset.py` + `services/member_support.py` | 反馈工单、一次性重置链接、只读交易排查（写审计） | 在后台修改会员账本；无邮件服务时假装已发送邮件 |
| 文章版本 | `models/article_version.py` + `services/article_version.py` | 每次保存追加快照，支持查看与恢复 | 覆盖历史；把版本记录当成草稿协作 |
| 内容对比与份额 | `app/fund_share_class.py` + `services/fund.py#compare` | 识别 A/C 等份额；2–3 只基金的费率/风险/区间对比 | 把不同份额当不同产品；把缺失风险指标当 0 |
| 持仓账本 | `services/ledger.py` | 买卖与公司行为按日期重放；**先全平台重放再投影**，各平台份额之和恒等于全基金份额 | 只把某个平台的事件喂进去重算；在多处各算一套余额 |
| 持仓工具 | `services/portfolio_tools.py` + `services/portfolio_provenance.py` | 历史导入、分红/拆分/转换流水（归属平台必填/幂等键+内容摘要/删除墓碑）、收益核对、CSV 导出、AI 账本快照 | 让导入覆盖已有流水；复制转出份额当转入份额；多平台靠猜归属；删除或补录后不校验整本账 |
| 会员活跃 | `models/member_activity.py` + `services/member_activity.py` + `repositories/engagement.py` | 按天记录访问（鉴权后节流打卡），窗口为"含今天 N 个自然日"，统一北京时间 | 用登录会话创建时间冒充访问；用 OR 拼多个"不以 X 结尾"导致过滤恒真 |
| 运行健康度 | `services/ops_health.py` + `scripts/backup_db.py` + `scripts/restore_drill.py` | 日志/备份/演练状态与告警；摘要按压缩文件字节计算，清单原子写入 | 在 API 进程里执行备份；把「有备份」当成「能恢复」；摘要与校验对象不一致 |
| 基金搜索 | `app/fund_search.py` + `repositories/fund.py` | 关键词分词、拼音/首字母、板块名映射；仓储层拼 SQL | 把拼音计算写进 SQL；在仓储里做业务判断 |
| 基金关注 | `app/repositories/favorite.py` + `services/favorite.py` | 会员自选：增删、列表、代码集合 | 把权限判断写进仓储 |
| 认证（双轨） | `services/auth.py`（AuthService/StaffAuthService） | 门户会员与后台员工各自登录/刷新/改密，共享密码与令牌原语 | 在一个 service 里混两张表 |
| 后台员工账号 | `models/staff.py` + `repositories/staff.py` + `api/v1/admin/staff.py` | staff_users 表的员工账号 CRUD（仅超管） | 员工与会员共用一张表 |
| 后台审计 | `app/api/middleware/audit.py` | 自动记录 `/admin/**` 写操作到 `audit_logs` | 在业务代码里手工埋点 |
| 运营统计 | `app/repositories/admin_stats.py` + `services/admin_stats.py` | 仪表盘聚合查询、系统信息 | 把展示格式化写进后端 |
| AI 能力 | `app/ai/` | 模型工厂、工具、智能体、工作流 | 绕过 service 改数据 | [README](../services/api/app/ai/README.md) |
| 迁移 | `alembic/` | 版本化表结构变更 | 手改线上库 | [README](../services/api/alembic/README.md) |
| 测试 | `tests/` | 接口与纯函数回归 | 依赖外部模型服务 | — |

## 前端模块

### apps/admin

| 模块 | 路径 | 职责 | 文档 |
| --- | --- | --- | --- |
| 接口层 | `src/api/` | axios 实例、拦截器、按模块的接口函数 | [README](../apps/admin/src/api/README.md) |
| 状态 | `src/stores/` | 跨页面共享状态（登录态、UI） | [README](../apps/admin/src/stores/README.md) |
| 页面 | `src/views/` | 交互与展示，按菜单分组组织子目录 | [README](../apps/admin/src/views/README.md) |
| 布局 | `src/layouts/` | 侧边栏（按分组聚合）+ 顶栏 + 面包屑 | [README](../apps/admin/src/layouts/README.md) |
| 路由 | `src/router/` | 路由表、`meta.group` 分组、守卫、标题 | [README](../apps/admin/src/router/README.md) |
| 后台类型 | `src/types/` | 仅管理端使用的视图类型（概览、审计） | — |
| 样式 | `src/styles/` | 设计变量与全局样式 | [README](../apps/admin/src/styles/README.md) |

### apps/portal

| 模块 | 路径 | 职责 | 文档 |
| --- | --- | --- | --- |
| 页面 | `app/pages/` | 文件路由，SEO meta | [README](../apps/portal/app/pages/README.md) |
| 组件 | `app/components/` | 可复用展示组件（自动导入） | [README](../apps/portal/app/components/README.md) |
| 数据 | `app/composables/` | 统一数据获取与解包 | [README](../apps/portal/app/composables/README.md) |
| 布局 | `app/layouts/` | 页头页脚骨架 | — |

### packages/shared

| 模块 | 路径 | 职责 | 文档 |
| --- | --- | --- | --- |
| 类型 | `src/types/` | 与后端 schema 对齐的接口类型 | [README](../packages/shared/src/README.md) |
| 常量 | `src/constants/` | 存储键、字典、业务码 | 同上 |
| 工具 | `src/utils/` | 日期、文本等纯函数 | 同上 |

## 我要加功能，从哪下手？

| 需求 | 落点 | 步骤 |
| --- | --- | --- |
| 加一个业务表 | models → schemas → repositories → services → api/v1 | 见 [development.md](development.md#新增一个后端业务模块以-product-为例) |
| 加一个后台页面 | `views/` + `api/` + `router/` | 见 [development.md](development.md#新增一个后台页面) |
| 加一个门户页面 | `app/pages/` | 见 [development.md](development.md#新增一个门户页面) |
| 加基金相关功能 | 见 [fund-module.md](fund-module.md) | 模型 → 采集 → 服务 → 接口 → 页面 |
| 换数据源 | `app/datasources/` | 实现 `FundDataProvider` 后在工厂切换 |
| 加一个 AI 工具 | `app/ai/tools/` | 见 [ai.md](ai.md#加一个工具) |
| 加一条确定性的 AI 流程 | `app/ai/graphs/` | 见 [ai.md](ai.md#加一条工作流) |
| 加一个共享工具函数 | `packages/shared/src/utils/` | 先确认两个 app 都要用 |
| 加一个权限点 | `deps.py` + `services/` | 权限判断不写在模板里 |
| 加一个定时任务 | `sync_schedules` + `services/sync_schedule.py`（进程内循环） | 规则写进表，不写 cron；见 [ADR-0015](adr/0015-in-process-sync-scheduler.md) |

## 判断标准：三问

1. **这段逻辑会被两个以上模块用到吗？** 会 → 上提到 service / shared；不会 → 就近放。
2. **换一个入口（REST → 定时任务 → AI 工具）还成立吗？** 不成立说明业务逻辑漏进了入口层。
3. **删掉这个模块，别的地方要不要改很多？** 要 → 边界没划清，重新拆。

## 模拟交易记账

新增 `models/fund_transaction.py`、`repositories/transaction.py`、`services/transaction.py`、
`services/portfolio_math.py` 和 `services/portfolio.py`，分别负责流水存储、数据查询、确认/作废、
Decimal 计算与组合汇总。入口为 `api/v1/portal/portfolio.py`。旧 positions 保留兼容，
不承载新账本。前端以 `usePortfolio.ts` / `useTradeForm.ts` 和 `components/portfolio/` 实现流程。
见 [交易流程](trading-flow.md) 与 [ADR-0011](adr/0011-confirmed-simulated-trade-ledger.md)。
