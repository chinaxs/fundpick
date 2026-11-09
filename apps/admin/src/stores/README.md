# 状态管理（admin/stores）

只放"跨页面"的状态。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `auth.ts` | token 持久化、当前用户、登录/登出、`isSuperuser` |
| `app.ts` | 侧边栏折叠等全局 UI 状态 |

## 约定
- 页面内的临时状态用 `ref`，不要进 store（否则状态来源变多，难以追踪）。
- store 里只做状态与派生（`computed`），不发 UI 提示。
- 刷新后需要保留的才写 localStorage（目前只有 token）。

## 扩展方式
新领域新建 `xxx.ts`，用 setup 语法（`defineStore('xxx', () => {...})`）。
**不要**建一个"全局公共 store"存放所有杂项。

## 依赖
上游：`api`、`@project/shared` ｜ 下游：`views`、`layouts`
