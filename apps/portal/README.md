# 拾贝门户（@project/portal）

Nuxt 4（SSR）· TypeScript。面向搜索引擎与首屏体验的基金数据站，数据来自 FastAPI 的 `/portal/**` 接口。

## 启动

```bash
pnpm --filter @project/portal dev      # http://localhost:3000
pnpm --filter @project/portal build    # 生产构建（Node Server）
pnpm --filter @project/portal generate # 纯静态导出（内容变化不频繁时可用）
```

## 目录

```
app/
├── assets/css/main.css     全局样式与设计变量
├── components/             AppHeader · AppFooter · ArticleCard
│                           FundNavChart · TypeBars · ReturnHistogram（自动导入）
├── composables/            usePortalApi · useFundApi（数据获取）
│                           useAuth（登录态）· useFavorites（自选）
├── layouts/default.vue     Header + 内容 + Footer
├── pages/                  文件路由
│   ├── index.vue           首页（市场概览 + 榜单）
│   ├── funds/index.vue     基金筛选排行
│   ├── funds/[code].vue    基金详情（净值曲线 + 区间指标）
│   ├── articles/           研报列表与详情
│   └── about.vue
├── app.vue
└── error.vue               404 / 服务异常页
```

## 数据获取

统一走 `composables/`，页面里不出现 URL：

```ts
const { data, pending } = await useFundList({ page: 1, period: '1y', sort_by: 'return' })
```

SSR 时于服务端发起请求，客户端激活后复用同一份 payload，不会重复请求。

## 会员体系

登录/注册走 Element Plus 弹窗（`AuthDialog`，全局单例），由 `useAuth().openAuth()` 唤起。

- 令牌存 **cookie**（`portal_at` / `portal_rt`）而不是 localStorage：
  SSR 阶段服务端要能读到，否则首屏会先渲染"未登录"再闪成已登录。
- access 2 小时、refresh 7 天；access 过期后 `ensureSession()` 自动用 refresh 续期。
- 门户注册的账号 `is_staff=False`，**不能登录后台**，也调不动 `/admin/**`。

详见 [ADR-0009](../../docs/adr/0009-portal-member-isolation.md)。

## 我的关注

`useFavorites()` 维护一份关注代码集合（`useState`），筛选页每行星标、详情页关注按钮
都读它，只请求一次 `/portal/favorites/codes`。

- 切换关注用**乐观更新**：先改本地集合让 UI 立刻响应，请求失败再整体回滚。
- 未登录点击关注会唤起登录弹窗（`openAuth('login')`），不会静默失败。
- 退出登录时调用 `reset()` 清空，避免下一个人看到上一个人的星标。

Element Plus 通过 `@element-plus/nuxt` 按需引入，只用在弹窗与菜单，
不整包进首屏；主站视觉仍由 `assets/css/main.css` 的设计变量控制。

## 请求链路与跨域

```
浏览器  --/api/v1/...-->  Nitro 反向代理  -->  http://127.0.0.1:8000/api/v1/...
SSR     -------------- 直连后端 ---------------------------------------->
```

浏览器侧用**同源相对路径**，由 `routeRules` 代理转发，因此不受 CORS 影响；
SSR 侧直连后端绝对地址。基址由 `useApiBase()` 按 `import.meta.server` 切换。

> 不要在前端改用绝对地址，也不要单靠后端 CORS 白名单放行。原因见
> [ADR-0007](../../docs/adr/0007-same-origin-proxy.md)。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NUXT_API_BASE` | `http://127.0.0.1:8000/api/v1` | 后端真实地址，供 SSR 与反代使用。容器部署填服务名 |
| `NUXT_PUBLIC_API_BASE` | `/api/v1` | 浏览器基址，**必须保持相对路径** |
| `NUXT_PUBLIC_API_DOCS_URL` | `http://127.0.0.1:8000/docs/portal` | 页脚接口文档链接（门户那份） |
| `NUXT_PUBLIC_ADMIN_URL` | `http://localhost:5174` | 页脚后台入口 |

生产若由 Nginx 统一入口反代 `/api/v1`，可移除 Nitro 代理，但前端基址仍保持 `/api/v1`。
