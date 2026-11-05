# 开发规范

## 分支与提交

- 主干 `main`，功能分支 `feat/xxx`，修复 `fix/xxx`。
- 提交信息遵循 Conventional Commits（已配置 commitlint + husky）：

```
feat(admin): 用户列表支持按状态筛选
fix(api): 修复文章 slug 冲突未去重
docs: 补充接口约定
```

- `pre-commit` 钩子对暂存文件跑 Prettier，`commit-msg` 校验提交格式。

## 代码风格

| 范围 | 工具 | 命令 |
| --- | --- | --- |
| 全仓格式 | Prettier | `pnpm format` |
| 前端检查 | oxlint + ESLint | `pnpm lint` |
| 后端检查 / 格式化 | Ruff | `cd services/api && make lint` / `make format` |
| 后端类型 | mypy | `make typecheck` |

## 新增一个后端业务模块（以 `product` 为例）

1. `app/models/product.py`：定义模型，继承 `Base`、`TimestampMixin`（需要时加 `SoftDeleteMixin`）
2. `app/models/__init__.py`：导出 `Product`，否则 Alembic 扫不到
3. `app/schemas/product.py`：`ProductCreate` / `ProductUpdate` / `ProductRead`
4. `app/repositories/product.py`：继承 `BaseRepository[Product]`，写专属查询
5. `app/services/product.py`：业务规则，**显式 `await session.commit()`**
6. `app/api/v1/admin/products.py`：路由，声明 `response_model=ApiResponse[...]`
   （面向门户的只读接口放 `app/api/v1/portal/`，探活类放 `common/`）
7. 在 `app/api/v1/admin/__init__.py` 里 `router.include_router(products.router)`
8. `make revision m="add product"` → 检查生成的迁移 → `make migrate`
9. `packages/shared/src/types/api.ts`：同步前端类型

## 新增一个后台页面

1. `src/views/xxx/XxxView.vue`
2. `src/api/index.ts` 增加接口函数（或在模块内新建）
3. `src/router/index.ts` 注册路由，`meta: { title, icon }`
4. `src/layouts/DefaultLayout.vue` 的 `menus` 增加菜单项

## 新增一个门户页面

在 `apps/portal/app/pages/` 下建 `.vue` 文件即生成路由；数据通过 `app/composables/usePortalApi.ts` 获取，SEO 用 `useSeoMeta`。

## 环境变量

| 位置 | 文件 | 说明 |
| --- | --- | --- |
| admin | `.env.development` / `.env.production` | `VITE_API_BASE_URL`、`VITE_PROXY_TARGET` |
| portal | `.env` | `NUXT_PUBLIC_API_BASE` |
| api | `.env` | 数据库、JWT、CORS 等，见 `.env.example` |

**`.env` 一律不入库**；新增变量时同步更新 `.env.example`。

## 数据库迁移

- 只允许通过 Alembic 变更表结构，不手工改库。
- 生成后**必须 review**：`compare_type` 已开启，注意 MySQL 的 `BigInteger` / `Boolean` 默认值差异。
- 迁移文件随代码一起提交；回滚用 `uv run alembic downgrade -1`。

## 测试

- 后端：`pytest` + `httpx.AsyncClient`（ASGI 直连，无需起服务）。
- 前端：`vitest`（admin 已配置）。
- CI（`.github/workflows/ci.yml`）会跑 lint、type-check、构建与后端测试。
