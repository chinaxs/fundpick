# 组件（portal/components）

Nuxt 自动导入，无需手动 import。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `AppHeader.vue` | 顶部导航：品牌、菜单、移动端汉堡、后台入口 |
| `AppFooter.vue` | 页脚：简介、站点/资源链接、版权 |
| `ArticleCard.vue` | 文章卡片：封面（无图时渐变占位）、标题、摘要、日期、浏览数 |

## 约定
- 只做展示，不发请求；数据通过 props 传入。
- props 必须声明类型（`defineProps<{...}>()`）。
- 样式 `scoped`，颜色取 `assets/css/main.css` 里的 CSS 变量（`var(--color-primary)`）。

## 扩展方式
新增通用组件放本目录即自动可用；仅某页用的小块留在页面文件内，不要过早抽象。

## 依赖
上游：`@project/shared`（类型与格式化）｜ 下游：`pages`、`layouts`

## 基金与工作台

- `funds/Filters.vue`：筛选条件与快捷入口，通过事件通知页面；样式见 `fund-filters.css`。
- `funds/Results.vue`：基金结果与表头排序，通过事件切换排序；样式见 `fund-results.css`。
- `workspace/Portfolio.vue`：模拟持仓概览与金额隐藏。
- `workspace/Watchlist.vue`：最近 5 只关注、区间表现与快捷买入。
- `workspace/Distributions.vue`：关注结构分布。

工作台样式限定在 `.workspace` 下，由 `workspace.css` / `workspace-charts.css` 提供。
这些组件只接收数据与发出事件，请求由页面调用 composables 完成。

`portfolio/` 为模拟交易的录入、预览、持仓、流水和旧记录核对组件；详见该目录 README。

`FundBuyButton.vue` 与 `HoldingBadge.vue` 在各基金展示位置提供买入/加仓和持仓标识；读取共享代码集合，不逐行请求。

`favorites/FundRow.vue` 展示关注基金的主要信息和买入/加仓，回撤与夏普由页面的风险指标开关控制。
工作台默认保留持仓概览与最近关注，结构分布按需展开。
