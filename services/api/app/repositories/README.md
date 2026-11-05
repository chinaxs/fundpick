# 仓储层（Repository）

只管"怎么查"，不管"能不能查"。

## 边界
- 负责：查询构造、CRUD、软删除过滤、分页、统计。
- 不负责：业务校验、抛 HTTP 异常、提交事务。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `base.py` | `BaseRepository`：`get` / `get_by` / `list` / `paginate` / `create` / `update` / `delete`（默认软删） |
| `user.py` | 用户名/邮箱查找、存在性判断、关键词分页 |
| `article.py` | slug 查询、已发布分页、后台分页、统计 |

## 扩展方式
优先用 `BaseRepository` 的通用方法；只有业务特有查询才新增方法。
返回值保持"模型或 `None`"，不要返回 dict 或已序列化数据。

## 依赖
上游：`models`、`db` ｜ 下游：`services`
