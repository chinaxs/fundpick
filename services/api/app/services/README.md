# 业务层（Service）

系统里唯一允许写"业务判断"的地方。

## 边界
- 负责：业务规则、状态流转、唯一性校验、事务提交（`await session.commit()`）、跨仓储编排。
- 不负责：HTTP 概念（`Request`/`HTTPException`/状态码）、SQL 拼装、响应序列化。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `auth.py` | 认证、签发令牌、修改密码 |
| `user.py` | 用户 CRUD、唯一性校验、密码重置 |
| `article.py` | 文章 CRUD、slug 去重、发布/撤回、浏览量（可关闭） |

## 扩展方式
新增资源时继承同样的写法：构造函数接收 `AsyncSession`，内部持有一个 repository。
一个方法 = 一个业务动作 = 一次 commit。写操作后如需返回最新字段（如 `updated_at`），显式 `await session.refresh(obj)`。

## 依赖
上游：`repositories`、`models`、`core` ｜ 下游：`api`、`ai`（工具层复用本层）

模拟交易由 `transaction.py` 持有确认与作废事务；`portfolio_math.py` 进行 Decimal 计算；`portfolio.py` 生成持仓、收益与旧持仓待核对清单。只有已确认有效流水计入新组合，旧 `portal_position.py` 用于兼容和旧记录。

`trade_timing.py` 以证券交易日历核对申请时间与净值日；`trade_application.py` 保存待确认记录，平台回执入账由 transaction 统一提交，真实份额与净到账不重算覆盖。

`automatic_trade.py` 从金额/时间重建自动交易，`automatic_lookup.py` 补查精确净值与费率缓存，`trade_fee_math.py` 处理外扣法和FIFO持有期费用。自动来源 estimated 与回执 receipt 区分；未知价格/费率保留待处理，不当零。

`trade_history.py` 统一申请/成交记录并按状态允许删除，保留请求墓碑；`automatic_trade` 依据公开T+N周期等待。
