# ADR-0009：门户会员与后台账号双重隔离

- 状态：已采纳
- 日期：2026-11-06
- 相关：[ADR-0008](0008-api-grouping-by-consumer.md)

## 背景

门户上线用户系统后，注册用户与后台运营账号落在同一张 `users` 表。
原实现只有 `is_superuser` 一个权限位，且后台接口的鉴权依赖是 `CurrentUser`（只校验"已登录"）。

于是出现一个真实漏洞：

1. 任何人在门户注册一个账号，就拿到合法 JWT；
2. 用这个 JWT 调 `POST /admin/auth/login` —— 密码是对的，登录成功；
3. 或者直接带着门户 token 调 `GET /admin/articles` —— `CurrentUser` 只要求登录，直接放行。

也就是说：**门户注册用户能进入后台**，虽然用户管理有 `SuperUser` 挡着，但内容管理、基金数据、AI 接口全部暴露。

## 决策

加两道闸，缺一不可。

**第一道：账号类型位**

```python
is_staff: Mapped[bool]  # 是否后台账号（可登录 /admin）
```

- 门户注册写死 `is_staff=False`（`PortalAuthService.register`）；
- 后台创建的用户默认 `is_staff=True`（`UserCreate` 默认值）；
- 后台登录要求 `require_staff=True`，非后台账号与密码错误返回同一句提示，不泄露账号类型。

**第二道：路由级依赖**

```python
StaffUser = Annotated[User, Depends(get_current_staff)]  # is_staff or is_superuser
```

`/admin/**` 下除登录与刷新外的所有端点都改用 `StaffUser`，替换原来的 `CurrentUser`。
即使令牌合法，非后台账号也会得到 403。

迁移时回填 `UPDATE users SET is_staff = 1 WHERE is_superuser = 1`，
否则存量超管升级后会被自己的新规则挡在门外。

## 为什么两道都要

| 只做类型位 | 只做路由依赖 |
| --- | --- |
| 登录能拦住，但已签发的旧 token 仍可用 | 能拦住接口，但后台登录本身仍对会员开放 |
| 新增后台接口时容易忘改依赖 | 新增接口时容易忘加依赖（默认无鉴权更容易发现） |

两道叠加后，即使某天有人新增后台端点时漏写 `StaffUser`，
`CurrentUser` 至少还能拦住匿名请求；而登录环节已经先一步拒绝了非后台账号。

## 备选方案

**拆成两张表**（`users` 与 `members`）：

- 优点：物理隔离，最彻底。
- 否决原因：当前唯一的差异就是"能否进后台"，两张表会带来重复的密码、令牌、
  登录逻辑。等门户会员出现专属属性（等级、积分、订阅状态）时再拆不迟，
  届时用一对一扩展表过渡，不必一步到位。

**用角色表 + RBAC**：

- 否决原因：现在只有两种角色，引入权限表属于过度设计。
  等出现"运营只能看内容、财务只能看报表"这类需求时再上。

## 代价

- 每个后台端点都要记得用 `StaffUser`，这是**约定而非强制**。
  已在 `app/api/README.md` 与 `CONVENTIONS.md` 写成硬性规则，
  并用测试 (`test_portal_token_cannot_access_admin_api`) 守住三个代表性端点。
- `users` 表多一个字段，查询时需注意别把 `is_staff` 泄露给门户接口
  （`PortalUserRead` 不含该字段）。

## 后续

门户会员专属功能（自选、组合、提醒）落地时，优先用扩展表
`member_profiles(user_id, ...)` 承载，避免主表继续膨胀。
