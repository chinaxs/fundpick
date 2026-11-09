# 布局（admin/layouts）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `DefaultLayout.vue` | 侧边栏（可折叠）+ 顶栏（面包屑、用户下拉）+ 内容区 `<router-view>` |

## 要点
- 菜单数组 `menus` 与路由 `meta.title/icon` 保持同步；新增页面记得加。
- 页面刷新后在此处调用 `authStore.fetchProfile()` 恢复用户信息。
- 退出登录走确认框，取消不抛错。

## 扩展方式
需要第二种骨架（如"全屏无侧边栏"）时新增 `XxxLayout.vue`，在路由里指定，不要用 `v-if` 在同一布局里切换。

## 依赖
上游：`stores`、`router` ｜ 下游：`views`（通过 router-view 渲染）
