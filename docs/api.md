# 接口约定

Base URL：`http://127.0.0.1:8000/api/v1`

## 接口分组

接口按**调用方**分三组，URL 前缀即归属，看地址就能判断权限要求：

| 前缀 | 调用方 | 鉴权 | 特征 |
| --- | --- | --- | --- |
| `/portal/**` | 门户网站（浏览器 + SSR） | 无 | 匿名只读，可公开缓存 |
| `/admin/**` | 后台管理 | 必须登录，部分需超管 | 含写操作与敏感数据 |
| `/health/**` | 负载均衡、监控 | 无 | 探活，无业务逻辑 |

两个前端严格对应：

- `apps/portal` **只**调用 `/portal/**`
- `apps/admin` **只**调用 `/admin/**`

门户将来会有自己的用户体系（自选、组合），届时登录入口为 `/portal/auth/**`，
与 `/admin/auth/**` 完全独立——两套身份不互通，避免后台账号能登进门户。

> 新增接口时先判断"谁在调用"，再放进对应路由包：
> `app/api/v1/{portal,admin,common}/`。不要平铺在 `router.py` 里。

## 统一响应

所有业务接口返回同一结构（HTTP 状态码同时表达语义）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "9f8c1e..."
}
```

| 字段 | 说明 |
| --- | --- |
| `code` | 业务码，`0` 成功；非 0 见下表 |
| `message` | 可直接展示给用户的提示 |
| `data` | 业务数据，失败时为 `null` 或校验详情 |
| `request_id` | 与响应头 `X-Request-ID` 一致，排查问题时提供此值 |

### 业务码

| code | HTTP | 含义 |
| --- | --- | --- |
| 0 | 200/201 | 成功 |
| 40100 | 401 | 未认证 / token 失效 |
| 40300 | 403 | 无权限 |
| 40400 | 404 | 资源不存在 |
| 40900 | 409 | 冲突（用户名重复等） |
| 42200 | 422 | 参数校验失败（`data` 为字段错误列表） |
| 50000 | 500 | 服务器内部错误 |
| 50300 | 503 | 依赖能力未就绪（如 AI 未配置密钥） |

## 分页

请求参数：`page`（从 1 开始）、`page_size`（1–100）。

```json
{ "items": [], "total": 128, "page": 1, "page_size": 20 }
```

## 鉴权（后台）

1. `POST /admin/auth/login`，body：`{ "username": "admin", "password": "..." }`（username 也接受邮箱）
2. 返回 `access_token`（默认 2 小时）、`refresh_token`（7 天）
3. 后续请求带 `Authorization: Bearer <access_token>`
4. 过期后用 `POST /admin/auth/refresh` 换新 token
5. `GET /admin/auth/me` 获取当前用户

门户接口**不需要**鉴权，直接请求即可。

## 接口清单

### 门户 · 会员（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/portal/auth/register` | 注册，成功后直接返回令牌（自动登录） |
| POST | `/portal/auth/login` | 登录（用户名或邮箱 + 密码） |
| POST | `/portal/auth/refresh` | 刷新令牌 |
| GET | `/portal/auth/me` | 当前会员（不含 `is_staff` 等内部字段） |
| POST | `/portal/auth/logout` | 语义化退出；JWT 无状态，客户端丢弃令牌即可 |

**门户注册的账号不能登录后台**：`is_staff=False`，后台登录返回 401；
即便持有有效 token，调用 `/admin/**` 也会得到 403。详见 [ADR-0009](adr/0009-portal-member-isolation.md)。

### 门户 · 自选（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/favorites` | 我的关注列表（分页，含所选区间指标） |
| GET | `/portal/favorites/codes` | 已关注代码列表，列表页标记星标用（一次拉全量，最多 500） |
| POST | `/portal/favorites` | 关注，body：`{ "code": "002910" }`；已关注时幂等 |
| DELETE | `/portal/favorites/{code}` | 取消关注 |

取消关注是**硬删除**：软删会占住 `(user_id, fund_id)` 唯一约束，导致取消后无法再次关注。

### 门户 · 基金（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/funds` | 筛选排行（keyword / type / risk_level / company_id / period / sort_by / sort_order） |
| GET | `/portal/funds/filters` | 筛选项字典（类型、风险、公司、区间、排序字段） |
| GET | `/portal/funds/{code}` | 基金详情（公司、经理、费率、规模） |
| GET | `/portal/funds/{code}/metrics` | 各区间指标（收益、回撤、波动、夏普、排名） |
| GET | `/portal/funds/{code}/navs` | 净值序列，支持 `period`（1m/3m/6m/1y/3y/all）与 `limit`（超限等距抽样） |

### 门户 · 统计（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/stats/overview` | 总数、公司数、类型分布与各类型平均收益 |
| GET | `/portal/stats/return-distribution` | 区间收益分布分桶（`period`，默认 `1y`） |

### 门户 · 内容（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/articles` | 已发布文章列表 |
| GET | `/portal/articles/{slug}` | 文章详情（浏览数 +1） |

### 后台 · 认证

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/admin/auth/login` | 公开 | 登录 |
| POST | `/admin/auth/refresh` | 公开 | 刷新令牌 |
| GET | `/admin/auth/me` | 登录 | 当前用户 |
| POST | `/admin/auth/change-password` | 登录 | 修改密码 |

### 后台 · 用户（超管）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 用户列表（keyword / is_active） |
| POST | `/admin/users` | 创建用户 |
| GET | `/admin/users/{id}` | 详情 |
| PATCH | `/admin/users/{id}` | 更新 |
| DELETE | `/admin/users/{id}` | 软删除 |

### 后台 · 内容

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/articles` | 文章列表（status / keyword） |
| POST | `/admin/articles` | 创建文章 |
| GET | `/admin/articles/{id}` | 详情 |
| PATCH | `/admin/articles/{id}` | 更新（含发布/撤回） |
| DELETE | `/admin/articles/{id}` | 软删除 |

### 后台 · 基金

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/funds` | 基金数据列表 |
| GET | `/admin/funds/sync-status` | 同步状态（基金总数、净值行数、最新净值日） |

### 后台 · AI

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/ai/status` | 能力状态（是否启用、模型、是否就绪） |
| POST | `/admin/ai/chat` | 内容助手对话（`message` + 可选 `thread_id`） |
| POST | `/admin/ai/review` | 文章质检（规则校验 + 模型建议） |

未配置模型密钥时返回 `503` / `code=50300`，不影响其他接口。

### 公共

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 存活探针 |
| GET | `/health/db` | 数据库连通性 |

## 文档入口

接口文档按消费方拆成两份，各自只展示自己那部分：

| 文档 | 地址 | 范围 |
| --- | --- | --- |
| 门户接口文档 | <http://127.0.0.1:8000/docs/portal> | `/portal/**` 共 9 个路径 |
| 后台接口文档 | <http://127.0.0.1:8000/docs/admin> | `/admin/**` 共 13 个路径 |
| 全量文档 | <http://127.0.0.1:8000/docs> | 全部 24 个路径，排查跨端问题时用 |

对应的 schema 分别是 `/openapi/portal.json`、`/openapi/admin.json`、`/openapi.json`。
切分在 `app/core/openapi.py` 里按路径前缀完成，**不拆服务、不复制路由**，新增接口自动归入对应文档。

## 约定细节

- 时间统一为 `YYYY-MM-DDTHH:MM:SS`（本地时区，无时区后缀），前端负责展示格式化。
- 删除为**软删除**（`deleted_at` 置位），列表默认过滤已删除数据。
- 文章 `slug` 唯一，留空时由标题生成；中文标题会退化为 `post-xxxxxxxx`。
- 列表接口的 `keyword` 为模糊匹配，后端做长度保护，避免全表扫描（可按需加索引）。
- 基金价格类字段（收益、净值）带正负号；**幅度类字段**（回撤、波动率）为正值，
  前端展示时不要加 `+`。
