# 0005 · shared 包保持框架无关

- **状态**：已采纳
- **日期**：2026-11-05

## 背景

`packages/shared` 被 admin（Vue SPA）和 portal（Nuxt SSR）同时引用。最初很容易把它写成"什么方便放什么"，
一旦里面出现 `import { ref } from 'vue'` 或 `localStorage`，Nuxt 的服务端渲染就会踩坑（`window is not defined`）。

## 决策

`shared` 只允许包含三类内容：**类型定义、常量、无副作用纯函数**。
禁止依赖 vue / nuxt / 浏览器 API，禁止发请求、读写存储、访问 `window`。

## 理由

1. SSR 安全：服务端没有 `window`/`localStorage`，任何副作用都会在渲染期报错。
2. 可测试：纯函数不依赖环境，vitest 直接跑。
3. 可移植：未来若加 React 版本或 Node CLI，shared 依然可用。

## 备选方案

| 方案 | 为什么不选 |
| --- | --- |
| 把 composable 也放 shared | 需要 vue 依赖，SSR 与版本耦合 |
| 每个 app 各自维护类型 | 接口改动时必然不同步，前端类型漂移 |

## 后果

- 好处：类型单一来源；SSR 稳定；测试成本低。
- 代价：需要"客户端专属逻辑"时要放到各 app 内（如 `stores`、`composables`），不能图省事塞 shared。
- 检查方式：`rg "from 'vue'|window\.|localStorage" packages/shared/src` 应无结果。
