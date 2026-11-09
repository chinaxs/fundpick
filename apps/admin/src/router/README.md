# 路由（admin/router）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `index.ts` | 路由表、`RouteMeta` 类型扩展、登录守卫、标题设置 |

## 约定
- `meta: { title, icon, public }`：`title` 用于面包屑与文档标题，`icon` 用于菜单，`public` 表示无需登录。
- 页面组件全部懒加载（`() => import(...)`），首屏只加载必要代码。
- 权限只做"是否登录"的粗粒度拦截；细粒度权限由后端校验（前端隐藏按钮只是体验优化）。

## 扩展方式
新增页面：加一条 `children` 记录，`name` 与菜单项一致，避免 `activeMenu` 高亮错乱。

## 依赖
上游：`views`、`layouts`、`@project/shared` ｜ 下游：`main.ts`、`layouts`
