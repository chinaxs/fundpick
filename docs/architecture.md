# 架构说明

## 全局视图

```
┌──────────────┐      ┌──────────────┐
│  admin (SPA) │      │ portal (SSR) │
│  Vue3 + Vite │      │    Nuxt 4    │
└──────┬───────┘      └──────┬───────┘
       │  HTTP/JSON (JWT)    │
       └──────────┬──────────┘
                  ▼
        ┌──────────────────┐
        │  FastAPI (8000)  │
        │  router/service  │
        │  /repository     │
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │ MySQL  test_study│
        └──────────────────┘
```

- 两个前端**不共享运行时**，只共享 `packages/shared` 的类型与常量（编译期）。
- 门户是只读消费方：仅调用 `/portal/**` 公开接口；后台调用 `/admin/**`（含 `/admin/auth/**`）需要登录。
  URL 前缀即归属，看地址就能判断权限要求。

## monorepo 依赖关系

```
apps/admin ──┐
             ├──▶ packages/shared (workspace:*)
apps/portal ─┘
services/api （独立 Python 工程，不参与 pnpm workspace）
```

`packages/shared` 通过 `tsc` 构建出 `dist/`，两个 app 引用其产物。修改后执行 `pnpm build:shared`（`pnpm dev` 已自动前置）。

## 后端分层

| 层 | 目录 | 职责 | 禁止 |
| --- | --- | --- | --- |
| 路由 | `app/api/v1/{portal,admin,common}` | 参数解析、鉴权依赖、调用 service、包装响应 | 写 SQL、写业务分支 |
| 服务 | `app/services` | 业务规则、事务提交、跨仓储编排 | 依赖 Request / HTTP 概念 |
| 仓储 | `app/repositories` | 查询构造、CRUD、软删除过滤 | 抛 HTTP 异常 |
| 模型 | `app/models` | 表结构、索引、关系 | 业务逻辑 |

横切能力：

- `core/config.py`：pydantic-settings 读取 `.env`，导出 `settings` 单例与 `database_url`。
- `core/security.py`：bcrypt 密码哈希 + PyJWT 签发/校验。
- `core/exceptions.py`：`AppException` 家族，携带 `status_code` / `code`。
- `core/logging.py`：控制台 + 滚动文件日志。
- `db/session.py`：`async_sessionmaker`，依赖注入时异常自动回滚；**commit 由 service 显式控制**。

## 一次请求的流向

```
GET /api/v1/admin/users
  → RequestContextMiddleware   注入 request_id、记录耗时
  → Depends(get_current_user)  解析 JWT、查用户、校验启用状态
  → Depends(get_current_superuser) 校验管理员权限
  → endpoint                   组装 UserQuery/PageParams
  → UserService.list           → UserRepository.search
  → ApiResponse[PageResult]    统一包装返回
```

## 前端分层（admin）

```
views/        页面级组件，只做交互与展示
  ↓ 调用
api/          接口函数（按模块拆分）+ client.ts（拦截器、解包）
  ↓ 使用
stores/       Pinia，跨页面状态（登录态、UI 状态）
```

- 所有请求经 `api/client.ts`：自动加 `Authorization`、解包 `data`、`code!=0` 抛错并提示、401 跳登录。
- 路由守卫基于 localStorage 的 token 做粗粒度拦截，细粒度权限在后端校验。

## 前端分层（portal）

- 文件路由：`app/pages/**` 自动生成路由。
- 数据获取集中在 `composables/usePortalApi.ts`，统一 `baseURL` 与响应解包。
- SSR 期间请求在后端发出，客户端复用同一份 payload（`useFetch` 机制），无重复请求。
