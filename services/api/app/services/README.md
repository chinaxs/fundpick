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
