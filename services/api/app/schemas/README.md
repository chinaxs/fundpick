# 契约层（Pydantic）

定义"进出系统长什么样"，同时是 OpenAPI 文档的来源。

## 边界
- 负责：请求/响应模型、字段校验、默认值、示例。
- 不负责：查库、业务判断。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `common.py` | `ApiResponse[T]`、`PageResult[T]`、`PageParams` |
| `user.py` | `UserCreate/Update/Read/Query` |
| `article.py` | `ArticleCreate/Update/Read/ListItem` |
| `auth.py` | 登录、令牌、改密模型 |

## 扩展方式
命名用后缀区分职责（`Create`/`Update`/`Read`/`Query`）；读模型加 `model_config = ConfigDict(from_attributes=True)`。
**契约变更要同步 `packages/shared/src/types/api.ts`**，否则前端类型会漂移。

## 依赖
上游：`models`（仅用于枚举引用）｜ 下游：`api`、`services`、`ai`
