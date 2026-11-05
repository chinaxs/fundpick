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
