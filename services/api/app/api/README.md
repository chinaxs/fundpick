# API 层（路由与依赖）

对外暴露 HTTP 接口，只做"翻译"：HTTP 语义 ↔ 业务调用。

## 边界
- 负责：参数解析与校验、鉴权依赖、调用 service、包装 `ApiResponse`、声明 `response_model`。
- 不负责：SQL、事务、业务规则、跨模块编排。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `deps.py` | `SessionDep` / `CurrentUser` / `SuperUser` / `RequestIdDep` |
| `v1/router.py` | 汇总所有子路由，新增模块在此挂载 |
| `v1/endpoints/health.py` | 存活与数据库探针 |
| `v1/endpoints/auth.py` | 登录、刷新、当前用户、改密 |
| `v1/endpoints/users.py` | 后台用户管理（需超管） |
| `v1/endpoints/articles.py` | 后台文章管理（需登录） |
| `v1/endpoints/portal.py` | 门户公开内容接口 |
| `v1/endpoints/ai.py` | AI 对话与质检 |

## 扩展方式
新增资源时复制 `articles.py` 的结构：查询参数用 `Query(...)` 声明约束，响应统一 `ApiResponse[T]`。
**不要**在这里写 `if 用户是管理员 then ...`，权限用依赖（`SuperUser`）表达。

## 依赖
上游：`schemas`、`services`、`core` ｜ 下游：无（最外层）
