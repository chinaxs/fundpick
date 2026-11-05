# 接口约定

Base URL：`http://127.0.0.1:8000/api/v1`

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

## 分页

请求参数：`page`（从 1 开始）、`page_size`（1–100）。

```json
{ "items": [], "total": 128, "page": 1, "page_size": 20 }
```

## 鉴权

1. `POST /auth/login`，body：`{ "username": "admin", "password": "..." }`（username 也接受邮箱）
2. 返回 `access_token`（默认 2 小时）、`refresh_token`（7 天）
3. 后续请求带 `Authorization: Bearer <access_token>`
4. 过期后用 `POST /auth/refresh` 换新 token
5. `GET /auth/me` 获取当前用户

## 接口清单

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/health` | 公开 | 存活探针 |
| GET | `/health/db` | 公开 | 数据库连通性 |
| POST | `/auth/login` | 公开 | 登录 |
| POST | `/auth/refresh` | 公开 | 刷新令牌 |
| GET | `/auth/me` | 登录 | 当前用户 |
| POST | `/auth/change-password` | 登录 | 修改密码 |
| GET | `/admin/users` | 管理员 | 用户列表（keyword / is_active） |
| POST | `/admin/users` | 管理员 | 创建用户 |
| GET/PATCH/DELETE | `/admin/users/{id}` | 管理员 | 详情 / 更新 / 软删除 |
| GET | `/admin/articles` | 登录 | 文章列表（status / keyword） |
| POST | `/admin/articles` | 登录 | 创建文章 |
| GET/PATCH/DELETE | `/admin/articles/{id}` | 登录 | 详情 / 更新 / 软删除 |
| GET | `/portal/articles` | 公开 | 已发布文章列表 |
| GET | `/portal/articles/{slug}` | 公开 | 文章详情（浏览数 +1） |

完整 OpenAPI：<http://127.0.0.1:8000/docs>

## 约定细节

- 时间统一为 `YYYY-MM-DDTHH:MM:SS`（本地时区，无时区后缀），前端负责展示格式化。
- 删除为**软删除**（`deleted_at` 置位），列表默认过滤已删除数据。
- 文章 `slug` 唯一，留空时由标题生成；中文标题会退化为 `post-xxxxxxxx`。
- 列表接口的 `keyword` 为模糊匹配，后端做长度保护，避免全表扫描（可按需加索引）。
