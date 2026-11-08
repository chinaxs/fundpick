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

`fund_transactions` 为已确认模拟交易与作废流水，含会员内唯一 request_key、费用、净值来源、份额及剩余成本快照；`fund_positions` 保留旧持仓供核对。

`trade_applications` 保存外部平台待确认申请；交易表新增平台、申请时间、净值所属日/平台确认日、回执编号及来源，旧折算来源保留。

`fund_fee_schedules` 缓存公开交易费率及查询时间/来源；自动交易的 calculation_basis 保存净值日、费用规则和持有批次依据。待处理申请 automatic_processing 区分自动补齐与人工确认。
