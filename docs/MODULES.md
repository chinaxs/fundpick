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
| 基金关注 | `app/repositories/favorite.py` + `services/favorite.py` | 会员自选：增删、列表、代码集合 | 把权限判断写进仓储 |
| AI 能力 | `app/ai/` | 模型工厂、工具、智能体、工作流 | 绕过 service 改数据 | [README](../services/api/app/ai/README.md) |
| 迁移 | `alembic/` | 版本化表结构变更 | 手改线上库 | [README](../services/api/alembic/README.md) |
| 测试 | `tests/` | 接口与纯函数回归 | 依赖外部模型服务 | — |

## 前端模块

### apps/admin

| 模块 | 路径 | 职责 | 文档 |
| --- | --- | --- | --- |
| 接口层 | `src/api/` | axios 实例、拦截器、按模块的接口函数 | [README](../apps/admin/src/api/README.md) |
| 状态 | `src/stores/` | 跨页面共享状态（登录态、UI） | [README](../apps/admin/src/stores/README.md) |
| 页面 | `src/views/` | 交互与展示 | [README](../apps/admin/src/views/README.md) |
| 布局 | `src/layouts/` | 侧边栏 + 顶栏骨架 | [README](../apps/admin/src/layouts/README.md) |
| 路由 | `src/router/` | 路由表、守卫、标题 | [README](../apps/admin/src/router/README.md) |
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
| 加一个定时任务 | 暂无（规划中） | 先提 ADR，不要随手加 `asyncio.create_task` |

## 判断标准：三问

1. **这段逻辑会被两个以上模块用到吗？** 会 → 上提到 service / shared；不会 → 就近放。
2. **换一个入口（REST → 定时任务 → AI 工具）还成立吗？** 不成立说明业务逻辑漏进了入口层。
3. **删掉这个模块，别的地方要不要改很多？** 要 → 边界没划清，重新拆。
