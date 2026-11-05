# 页面（admin/views）

## 结构
| 路径 | 页面 |
| --- | --- |
| `LoginView.vue` | 登录（表单校验 + 跳转回原页面） |
| `DashboardView.vue` | 仪表盘（统计卡片 + 结构速览） |
| `users/UserListView.vue` | 用户列表：搜索、分页、新建/编辑弹窗、软删除 |
| `articles/ArticleListView.vue` | 文章列表：状态筛选、发布/撤回、编辑弹窗 |
| `NotFoundView.vue` | 404 |

## 约定
- 页面不直接请求接口（走 `@/api`），不写复杂业务规则。
- 列表页统一三态：`loading`（`v-loading`）、空态、错误（拦截器已提示）。
- 弹窗表单用 `el-form` + `rules`，提交前 `validate()`。
- 二次确认（删除/发布）统一 `ElMessageBox.confirm(...).catch(() => false)`，取消不应抛异常。

## 扩展方式
新增页面：在 `views/` 建目录 → 写组件 → 注册路由 → 加侧边栏菜单（`layouts/DefaultLayout.vue`）。

## 依赖
上游：`api`、`stores`、`@project/shared` ｜ 下游：`router`
