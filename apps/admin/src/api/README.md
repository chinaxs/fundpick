# 接口层（admin/api）

页面访问后端的唯一入口。

## 边界
- 负责：axios 实例、请求/响应拦截、业务码解包、按模块分组的接口函数。
- 不负责：页面状态、UI 提示文案之外的业务判断。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `client.ts` | 实例配置、注入 token、401 跳登录、`code!=0` 抛错、`api.get/post/patch/delete` |
| `index.ts` | `authApi` / `userApi` / `articleApi`，类型全部来自 `@project/shared` |

## 扩展方式
新增接口：在 `index.ts` 对应分组加一个方法，返回类型写清楚。
**不要**在页面里 `axios.get()`，也不要新建第二个实例。

## 依赖
上游：`@project/shared` ｜ 下游：`views`、`stores`
