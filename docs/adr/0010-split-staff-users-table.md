# ADR-0010：后台员工拆分到独立的 staff_users 表

- 状态：已采纳
- 日期：2026-11-06
- 取代：[ADR-0009](0009-portal-member-isolation.md)

## 背景

ADR-0009 用 `users.is_staff` 标志位 + `StaffUser` 依赖实现了门户会员与后台账号的
逻辑隔离，堵住了"注册用户进后台"的漏洞。但两张身份仍然共用一张表，
随着后台功能成型，代价开始显现：

1. **语义混乱**：`/admin/users`（用户管理）名义上管"用户"，
   实际混着会员与员工，创建用户的表单还默认 `is_staff=True`——
   从后台建出来的"用户"根本不是官网会员；
2. **字段漂移**：员工需要"姓名、最近登录后台时间"，会员需要"昵称、注册来源"，
   一张表两头迁就，字段越加越脏；
3. **生命周期耦合**：员工离职要禁用账号，但这行记录同时还是某人的门户会员，
   禁用会顺带把他官网自选也冻结掉；
4. **鉴权靠约定**：`is_staff` 是数据位，哪张表都能查，审计与统计要小心
   不要把它泄露给门户响应。

## 决策

**物理拆表 + 令牌 scope 双保险。**

### 1. 两张独立的表

| 表 | 身份 | 登录入口 | 写入方 |
| --- | --- | --- | --- |
| `users` | 门户会员 | `/portal/auth/login` | 门户注册、后台会员管理 |
| `staff_users` | 后台员工 | `/admin/auth/login` | 后台账号管理（仅超管） |

- `users` 删除 `is_staff` / `is_superuser`，成为纯会员表；
- `staff_users` 保留 `is_superuser`（后台内部的三层权限：匿名 → 员工 → 超管）；
- 迁移（`c3f8a1d92b47`）把 `is_staff=1 OR is_superuser=1` 的行**搬走并从 users 删除**，
  是迁移不是复制。

### 2. 令牌 scope

```python
create_token(user.id, "access", scope="staff")   # 后台签发
create_token(user.id, "access", scope="portal")  # 门户签发
```

解码端（`deps.py`）在查库**之前**先校验 scope：
即使两张表主键撞号、令牌不伪造，也解不出对方的身份——
门户令牌调 `/admin/**` 得 401，员工令牌调 `/portal/auth/me` 同样 401。
这不是深度防御，是第一道闸：scope 错根本走不到查库那一步。

### 3. 认证服务双轨

`AuthService`（门户，users 表）与 `StaffAuthService`（后台，staff_users 表）
各自维护 login / refresh / change_password，共享密码哈希与令牌签发原语
（`issue_tokens(user_id, scope)`），密码策略与有效期不会漂移。

### 4. 后台账号管理接口

新增 `/admin/staff`（仅超管）：员工账号的增删改查与批量删除，
批量删除操作者本人自动跳过。`/admin/users` 语义收窄为纯门户会员管理。

## 为什么当初的否决理由不再成立

ADR-0009 否决拆表的理由是"差异只有一个 is_staff，拆表要重复密码、令牌、登录逻辑"。
现在：

- 差异不再是一个标志位，而是**两套字段、两种生命周期**（员工姓名 vs 会员昵称，
  离职禁用 vs 封号）；
- "重复登录逻辑"被共享原语化解（服务双轨但原语单份，见上）；
- 出现了"管理后台账号"这个真实需求，一张表时它无处安放。

## 代价

- 员工不能再用自己的账号登录门户看前台数据（原来"顺带"能登）。
  如有此需求，应单独注册会员账号——这正是拆表想明确的边界；
- 旧令牌（无 scope 声明）全部失效，升级后需要重新登录，一次性成本；
- 两张表都要做唯一性校验（用户名/邮箱），不能互相查重（`admin` 这个名字
  现在可以同时是员工登录名和某个会员的注册名，属于预期行为）。

## 守护测试

- `test_staff_token_cannot_access_portal` / `test_portal_token_cannot_access_admin_api`
  —— scope 双向隔离；
- `test_portal_account_cannot_login_admin` / `test_staff_account_cannot_login_portal`
  —— 两边登录入口互相不认账号；
- `test_staff_crud_requires_superuser` —— 员工账号管理仅超管；
- `test_user_batch_delete_protects_self` —— 批量删员工不能删掉自己。
