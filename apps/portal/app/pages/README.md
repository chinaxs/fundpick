# 页面（portal/pages）

Nuxt 文件路由，文件名即路径。

## 结构
| 文件 | 路由 | 说明 |
| --- | --- | --- |
| `index.vue` | `/` | 首页：Hero、特性、最新 3 篇 |
| `articles/index.vue` | `/articles` | 资讯列表 + 分页（`?page=`） |
| `articles/[slug].vue` | `/articles/:slug` | 详情：SSR 拉取、Markdown 渲染、动态 SEO meta |
| `about.vue` | `/about` | 关于页（技术栈与目录说明） |

## 约定
- 数据一律通过 `composables/usePortalApi.ts` 获取，不直接 `$fetch`。
- 每页必须设置 `useSeoMeta({ title, description })`，详情页用函数形式（依赖异步数据）。
- 404 用 `throw createError({ statusCode: 404, fatal: true })`，由 `app/error.vue` 渲染。

## 扩展方式
新增页面：建 `.vue` 文件即生成路由；若需出现在导航，改 `components/AppHeader.vue` 的 `navs`。

## 依赖
上游：`composables`、`components`、`@project/shared` ｜ 下游：无

## 基金研究与个人工作台

- `/funds`：可分享的基金筛选，筛选交互委托 `useFundScreener`，过滤器和表格按职责拆分。
- `/dashboard`：模拟持仓优先、关注表现其次，结构分析按需展开；会员私有页标记 noindex。
- `/favorites`、`/positions`：完整关注清单与持仓编辑，工作台提供入口。

产品取舍与商业化初评见 [product-review.md](../../../../docs/product-review.md)。

`/positions` 已改为已确认模拟买卖账本：买入→预览→确认→持仓汇总，卖出从持仓行发起，包含流水、作废与旧持仓核对。见 [trading-flow.md](../../../../docs/trading-flow.md)。

工作台页面精简为模拟持仓三项指标（市值、持有收益、累计收益）和最近关注预览，结构分析默认折叠。
关注页使用紧凑清单，风险指标按需开启；行数据由服务端快照与当前关注代码集合派生，
取消失败可恢复，末页清空时自动回退并刷新。
