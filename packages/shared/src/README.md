# @project/shared

前后端共享的**类型、常量、纯函数**。两个前端通过 `workspace:*` 引用其 `dist/` 产物。

## 边界（硬约束）
- 只允许：类型定义、常量、无副作用纯函数。
- 禁止：依赖 vue/nuxt/浏览器 API；发请求；读写 `localStorage`；`window.*`。
  原因见 [ADR-0005](../../../docs/adr/0005-package-boundaries.md)：Nuxt SSR 在服务端没有 `window`。

## 结构
| 目录 | 内容 |
| --- | --- |
| `types/api.ts` | 与后端 Pydantic 模型对齐的接口类型 |
| `constants/index.ts` | `API_PREFIX`、`STORAGE_KEYS`、`BIZ_CODE`、`ARTICLE_STATUS_MAP`、分页常量 |
| `utils/format.ts` | `formatDate` / `formatDateTime` / `fromNow` / `truncate` / `toSlug` |
| `index.ts` | 统一导出 |

## 扩展方式
1. 判断是否"两个 app 都要用"，只有一个用就别放这里；
2. 改完执行 `pnpm build:shared`（`pnpm dev` 已自动前置）；
3. 后端 schema 变更时同步 `types/api.ts`，这是唯一需要人工保证的同步点。

## 自检
```bash
rg "from 'vue'|window\.|localStorage" packages/shared/src   # 应无结果
```

## 依赖
无运行时依赖 ｜ 下游：`apps/admin`、`apps/portal`
