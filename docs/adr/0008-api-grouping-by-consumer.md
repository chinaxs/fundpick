# ADR-0008：接口按调用方分组（portal / admin / common）

- 状态：已采纳
- 日期：2026-11-06
- 相关：[ADR-0003](0003-layered-async-backend.md)

## 背景

业务扩张后接口变成三类：门户消费的公开数据、后台管理的读写操作、以及探活。
但路由是按业务域平铺的：

```
/api/v1/portal/funds      ← 有前缀
/api/v1/portal/stats
/api/v1/admin/users       ← 有前缀
/api/v1/admin/articles
/api/v1/auth/login        ← 游离
/api/v1/ai/chat           ← 游离
```

`/auth` 和 `/ai` 看不出服务谁。实际它们只给后台用：门户没有登录入口，
AI 接口全部要求 `CurrentUser`。结果联调时需要翻代码才能确认权限，
新人容易把 `/auth/login` 误当成"通用登录"而接进门户。

目录同样混乱：`endpoints/` 下平铺 `portal_funds.py`、`admin_funds.py`、
`articles.py`，只能靠文件名前缀猜归属。

## 决策

**按调用方分组，URL 前缀即归属。**

```
/api/v1/portal/**   门户：匿名只读，可公开缓存
/api/v1/admin/**    后台：必须登录，部分需超管（含 /admin/auth、/admin/ai）
/api/v1/health/**   探活：无鉴权，供监控
```

代码目录同步：

```
app/api/v1/
├── common/   health.py
├── portal/   funds.py · stats.py · articles.py
└── admin/    auth.py · users.py · articles.py · funds.py · ai.py
```

前缀在包的 `__init__.py` 统一声明，子文件只写相对路径。

## 备选方案

**按业务域分组**（`/funds/*`、`/users/*`、`/auth/*`，用 `?scope=admin` 区分）：

- 优点：资源路径短，符合 REST 直觉。
- 否决原因：把"谁能访问"藏进参数或中间件，权限判断不可见。
  同一个 `/funds` 既可能匿名可读、又可能需登录写入，靠代码而非 URL 表达，
  缓存策略、网关规则、日志审计都无法按前缀统一处理。

**保持现状只补文档**：

- 否决原因：文档会过期，URL 不会。归属信息应该长在接口地址上。

## 影响

- 破坏性变更：`/auth/*` → `/admin/auth/*`，`/ai/*` → `/admin/ai/*`。
  后端、后台前端、测试、文档同步修改；门户不受影响（`/portal/*` 未变）。
- 网关与缓存可以按前缀配置：`/portal/**` 可缓存、`/admin/**` 禁止缓存。
- 文档可以按同样边界拆分：`/docs/portal` 与 `/docs/admin` 各自只含本组接口，
  切分在 `app/core/openapi.py` 按前缀完成，新增接口自动归入对应文档。
- 门户将来启用自有用户体系时，登录入口是 `/portal/auth/**`，
  与 `/admin/auth/**` 天然隔离，不会出现"后台账号能登进门户"的越权问题。

## 需要遵守

1. 新增接口先判断"谁在调用"，放进对应包，不要平铺回 `router.py`。
2. `portal/` **禁止**引入 `CurrentUser`，`admin/` **禁止**出现无鉴权端点。
3. 新路由的 tag 同步登记到 `app/main.py` 的 `OPENAPI_TAGS`，否则 Swagger 分组缺描述。
