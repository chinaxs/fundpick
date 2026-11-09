# 数据连接（db）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `session.py` | `create_async_engine`、`async_session_factory`、`get_session` 依赖、`dispose_engine` |
| `base.py` | `Base`（DeclarativeBase）、`TimestampMixin`、`SoftDeleteMixin` |

## 要点
- `expire_on_commit=False`：commit 后仍可读取对象属性（异步下避免隐式懒加载）。
- `pool_pre_ping=True`：取连接前探活，规避 MySQL 8 小时断连。
- `get_session` 只负责异常回滚，**提交由 service 决定**。
- 新增全局模型字段（如 `deleted_at` 规则）改 Mixin，不要逐个模型加。

## 依赖
上游：`core.config` ｜ 下游：`models`、`repositories`、`services`、`ai.tools`
