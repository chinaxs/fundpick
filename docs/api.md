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

门户有自己的用户体系（注册、自选），登录入口为 `/portal/auth/**`，
与 `/admin/auth/**` 完全独立——**两张不同的表**（`users` / `staff_users`），
令牌各自带 `scope`（`portal` / `staff`），解码端强校验，两套身份互不通用：
门户令牌调 `/admin/**` 返回 401，员工令牌调 `/portal/auth/me` 同样 401。

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

## 鉴权（后台，staff_users 表）

1. `POST /admin/auth/login`，body：`{ "username": "admin", "password": "..." }`（username 也接受邮箱）
2. 返回 `access_token`（默认 2 小时）、`refresh_token`（7 天），令牌 `scope=staff`
3. 后续请求带 `Authorization: Bearer <access_token>`
4. 过期后用 `POST /admin/auth/refresh` 换新 token
5. `GET /admin/auth/me` 获取当前员工

门户会员接口走 `/portal/auth/**`（`users` 表，令牌 `scope=portal`），两套账号互不通用。

## 接口清单

### 门户 · 会员（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/portal/auth/register` | 注册，成功后直接返回令牌（自动登录） |
| POST | `/portal/auth/login` | 登录（用户名或邮箱 + 密码） |
| POST | `/portal/auth/refresh` | 刷新令牌 |
| GET | `/portal/auth/me` | 当前会员（只含展示字段，无内部状态） |
| POST | `/portal/auth/logout` | 语义化退出；JWT 无状态，客户端丢弃令牌即可 |

**门户注册的账号不能登录后台**：账号只存在 `users` 表，后台登录（查 `staff_users`）返回 401；
即便持有有效 token（`scope=portal`），调用 `/admin/**` 也会得到 401。详见 [ADR-0009](adr/0009-portal-member-isolation.md)。

### 门户 · 自选（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/favorites` | 我的关注列表（分页，含所选区间指标） |
| GET | `/portal/favorites/codes` | 已关注代码列表，列表页标记星标用（一次拉全量，最多 500） |
| POST | `/portal/favorites` | 关注，body：`{ "code": "002910" }`；已关注时幂等 |
| DELETE | `/portal/favorites/{code}` | 取消关注 |

取消关注是**硬删除**：软删会占住 `(user_id, fund_id)` 唯一约束，导致取消后无法再次关注。

### 门户 · 会员中心（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/me/dashboard?period=1y` | 工作台聚合：关注数/平均收益/正收益占比/夏普、类型/风险/板块/收益分布、收益榜与最近关注 |
| PATCH | `/portal/me` | 更新资料：仅 `email` / `full_name` / `avatar_url`，用户名与状态不可改 |
| POST | `/portal/me/change-password` | 修改密码，校验原密码；JWT 无状态，已签发令牌继续有效至过期 |
| POST | `/portal/me/deactivate` | 注销账号：body `{password}` 二次校验 → 清空关注 → 软删用户，旧令牌立即失效 |

全部接口只作用于 `CurrentUser`（令牌 `scope=portal`），不接收 `user_id`，从设计上杜绝越权。
工作台统计一次 join 取回关注基金后在内存分组（关注数上限 500），避免 6 条 GROUP BY SQL。

### 门户 · 基金（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/funds` | 筛选排行（keyword / type / risk_level / **sector** / company_id / period / sort_by / sort_order） |
| GET | `/portal/funds/filters` | 筛选项字典（类型、风险、**板块含数量**、公司、区间、排序字段） |
| GET | `/portal/funds/{code}` | 基金详情（公司、经理、费率、规模） |
| GET | `/portal/funds/{code}/metrics` | 各区间指标（收益、回撤、波动、夏普、排名） |
| GET | `/portal/funds/{code}/navs` | 净值序列，支持 `period`（1m/3m/6m/1y/3y/all）与 `limit`（超限等距抽样） |
| GET | `/portal/funds/{code}/holdings` | 季度重仓股（`quarter` 缺省取最新；本地无数据时实时回填） |

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

### 后台 · 认证（staff_users 表）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/admin/auth/login` | 公开 | 员工登录（令牌 scope=staff） |
| POST | `/admin/auth/refresh` | 公开 | 刷新令牌 |
| GET | `/admin/auth/me` | 登录 | 当前员工 |
| POST | `/admin/auth/change-password` | 登录 | 修改密码 |

### 后台 · 员工（仅超管，staff_users 表）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/staff` | 员工列表（keyword / is_active） |
| POST | `/admin/staff` | 创建员工账号（可指定超管） |
| GET | `/admin/staff/{id}` | 详情 |
| PATCH | `/admin/staff/{id}` | 更新（含重置密码 / 禁用 / 升降超管） |
| DELETE | `/admin/staff/{id}` | 软删除 |
| POST | `/admin/staff/batch-delete` | 批量软删除，body `{ids:[1..100]}`；操作者本人自动跳过 |

### 后台 · 用户（超管，门户会员 users 表）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 会员列表（keyword / is_active） |
| POST | `/admin/users` | 创建会员 |
| GET | `/admin/users/{id}` | 详情 |
| PATCH | `/admin/users/{id}` | 更新 |
| DELETE | `/admin/users/{id}` | 软删除 |
| POST | `/admin/users/batch-delete` | 批量软删除，body `{ids:[1..100]}` |

### 后台 · 内容

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/articles` | 文章列表（status / keyword） |
| POST | `/admin/articles` | 创建文章 |
| GET | `/admin/articles/{id}` | 详情 |
| PATCH | `/admin/articles/{id}` | 更新（含发布/撤回） |
| DELETE | `/admin/articles/{id}` | 软删除 |
| POST | `/admin/articles/batch-delete` | 批量软删除 |
| POST | `/admin/articles/batch-status` | 批量发布 / 撤回，body `{ids, status}` |

批量操作返回 `data.affected`（实际受影响行数，不存在的 ID 被跳过）。

### 后台 · 概览（登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/dashboard` | 运营概览：核心计数、数据覆盖率、类型分布、最近用户与最近操作，一次返回 |
| GET | `/admin/system/info` | 系统信息（**仅超管**）：运行环境、Python 版本、启动时间、各业务表行数 |

### 后台 · 审计（仅超管）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/audit-logs` | 操作日志查询（username 模糊 / resource / status_code / 时间范围，分页） |

后台所有写操作（`POST/PATCH/PUT/DELETE`，路径前缀 `/admin/**`）由
`AuditMiddleware` 自动落库到 `audit_logs` 表，业务代码零埋点。
记录内容：操作人、动作、资源、状态码、IP、耗时；**不记录请求体**（避免密码/令牌泄漏）。
登录成功后回填操作人，失败尝试仅保留 IP，可用于暴力破解排查。

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
| 门户接口文档 | <http://127.0.0.1:8000/docs/portal> | `/portal/**` |
| 后台接口文档 | <http://127.0.0.1:8000/docs/admin> | `/admin/**` |
| 全量文档 | <http://127.0.0.1:8000/docs> | 全部路径，排查跨端问题时用 |

对应的 schema 分别是 `/openapi/portal.json`、`/openapi/admin.json`、`/openapi.json`。
切分在 `app/core/openapi.py` 里按路径前缀完成，**不拆服务、不复制路由**，新增接口自动归入对应文档。

## 约定细节

- 时间统一为 `YYYY-MM-DDTHH:MM:SS`（本地时区，无时区后缀），前端负责展示格式化。
- 删除为**软删除**（`deleted_at` 置位），列表默认过滤已删除数据。
- 文章 `slug` 唯一，留空时由标题生成；中文标题会退化为 `post-xxxxxxxx`。
- 列表接口的 `keyword` 为模糊匹配，后端做长度保护，避免全表扫描（可按需加索引）。
- 基金价格类字段（收益、净值）带正负号；**幅度类字段**（回撤、波动率）为正值，
  前端展示时不要加 `+`。
- **费率语义**：`fee_rate` = 管理费率、`custody_fee` = 托管费率（均 %/年，来自雪球费用明细）。
  采集不到时为 `null`，前端显示 `—`，**绝不写 0 兜底**——排行接口的"手续费"是申购费
  （C 类为 0），与管理费是两回事，不能混用。
- 重仓股 `rank` 不信任数据源的"序号"（有时是季度内排名、有时是全年累计），
  采集时按季度分组、占净值比例降序重排。
- **风险等级与主题板块都是"规则推导"，不是官方定级/分类**（无公开数据源）：
  - `risk_level` 按基金类型推导（`sync_funds.py --mode risk-level`）：货币→低、债券→中低、
    FOF→中、混合/指数→中高、股票/QDII→高，只填 NULL。口径同支付宝 R1–R5 适当性分类。
  - `sector` 按基金简称/全称/跟踪指数关键词推导（`--mode sector`，规则集中在
    `app/fund_sectors.py`），特异度高的主题优先（半导体 > 科技、新能源 > 制造）。
    无主题词则保持 NULL（前端显示"综合"）；`--force` 可按最新规则全量重算。
    识别前必须剥离"证券投资基金"等通用后缀，否则"证券"会把全库误判为金融板块。
