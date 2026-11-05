# 样式（admin/styles）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `variables.scss` | 设计变量：主色、语义色、文本色、背景、圆角、阴影、布局尺寸 |
| `index.scss` | 全局重置 + 通用类（`.page` `.card` `.filter-bar` `.table-footer`） |

## 约定
- 颜色/间距/圆角**必须**用变量，禁止散落 `#2b6cb0`、`16px` 这类魔法值。
- 组件样式默认 `scoped`；覆盖 Element Plus 用 `:deep()`。
- `variables.scss` 已通过 Vite `additionalData` 全局注入，组件内直接用 `$color-primary`，无需 import。

## 扩展方式
加主题色：改 `variables.scss` 一处即可；如需暗色模式，新增 `theme-dark.scss` 并用 CSS 变量承载。

## 依赖
无（被所有组件引用）
