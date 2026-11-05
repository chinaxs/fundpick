# 基础设施（core）

与业务无关的横切能力，任何模块都可以依赖它，但它不依赖任何业务模块。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `config.py` | `Settings`（pydantic-settings），含 `database_url`、`ai_ready` 派生属性 |
| `security.py` | bcrypt 密码哈希、PyJWT 签发与校验 |
| `exceptions.py` | `AppException` 家族（401/403/404/409/422/503） |
| `logging.py` | 控制台 + 滚动文件日志 |

## 约定
- 新增配置项：加字段 + 更新 `.env.example` + 在文档写清默认值。
- 新增异常类型：继承 `AppException`，分配**新的** `code`，不要复用。
- 不要在 core 里 import services/models，否则会形成环。

## 依赖
上游：无 ｜ 下游：所有模块
