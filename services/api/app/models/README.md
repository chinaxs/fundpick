# 模型层（SQLAlchemy）

数据库结构的唯一来源，Alembic 迁移由它生成。

## 边界
- 负责：表名、字段、类型、索引、唯一约束、注释、软删除标记。
- 不负责：业务逻辑（可以有 `__repr__` 与简单 property）。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `user.py` | `users`：账号、密码哈希、角色、启用状态、最后登录 |
| `article.py` | `articles`：标题、slug、摘要、正文、状态、浏览量、发布时间 |
| `__init__.py` | **统一导出（新增模型必须在此登记）** |

## 扩展方式
1. 新建 `xxx.py`，继承 `TimestampMixin, SoftDeleteMixin, Base`；
2. 在 `__init__.py` 导出；
3. `make revision m="add xxx"` 生成迁移并 review。
枚举字段用 `StrEnum` + `values_callable`，保证库里存的是 `published` 而不是 `PUBLISHED`。

## 依赖
上游：`db.base` ｜ 下游：`repositories`、`services`、`alembic`
