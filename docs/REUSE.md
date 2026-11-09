# 复用优先（REUSE）

> 规矩很简单：**动手写之前，先花 10 分钟证明"没有现成的"**。
> 没有这 10 分钟，三个月后仓库里会有 5 个功能重叠的工具函数和 3 套半成品分页。

## 1. 检索顺序：由内向外

### 第一层：本仓库是否已有？

```bash
# 搜函数/类/组件名（含中文注释）
rg -n "分页|paginate" --type py
rg -n "formatDate|formatDateTime" -g "*.ts" -g "*.vue"

# 搜后端已有能力
rg -n "class .*Service" services/api/app/services
rg -n "@router\.(get|post)" services/api/app/api

# 搜前端已有组件
rg -n "defineProps" apps/*/src apps/portal/app/components
```

判断标准：**名字不同但语义相同**也算已有（比如 `paginate` 和 `page_result` 是同一件事）。

### 第二层：已安装的依赖里是否已有？

| 场景 | 先查 | 常见现成能力 |
| --- | --- | --- |
| 日期/数字格式化 | `packages/shared/src/utils`、`Intl` | 浏览器内置 `Intl.DateTimeFormat` |
| 表单校验 | Pydantic / Element Plus `rules` | 不要手写正则集合 |
| 重试/超时 | `tenacity`（后端已装）、axios `timeout` | 不要写 `while True + sleep` |
| 分页 | `BaseRepository.paginate` | 不要每个模块写一遍 |
| HTTP 客户端 | `src/api/client.ts` | 不要新建 axios 实例 |
| 数组/对象处理 | `lodash-es`（按需）或原生方法 | 简单场景别引库 |
| Markdown 渲染 | 后端已有简易渲染；复杂需求用 `marked` | 不要写正则地狱 |

```bash
# 前端：看某个包是否已在依赖树里
pnpm why <package>
pnpm list --depth 0

# 后端：看已装的包
uv pip list | grep -i <keyword>
```

### 第三层：社区是否已有成熟方案？

| 渠道 | 适用 | 怎么搜 |
| --- | --- | --- |
| PyPI | Python 库 | `uv pip index versions <name>`、<https://pypi.org> |
| npm | JS 库 | `npm view <name>`、<https://www.npmjs.com> |
| GitHub | 找实现参考、看 issue | `topic:fastapi` + 按 stars 排序、看最近提交 |
| Awesome 列表 | 找同类方案的横向对比 | `awesome-fastapi`、`awesome-vue`、`awesome-langchain` |
| 官方文档 | 优先于博客 | FastAPI / Nuxt / LangChain 官方 docs |

**搜 GitHub 时的三个硬指标**（缺一不可）：

1. 最近 6 个月有提交（不是归档项目）；
2. stars > 500 或属于知名组织（避免踩坑后无人维护）；
3. 打开 issue 列表，看是否有长期未处理的严重 bug。

## 2. 评估：引入一个依赖前必须回答

| 维度 | 问题 | 红线 |
| --- | --- | --- |
| 维护状态 | 最近提交？issue 响应？ | 归档 / 一年无更新 → 不用 |
| 许可证 | MIT / Apache-2.0 / BSD？ | GPL/AGPL 用于商业闭源 → 法务确认 |
| 体积 | 前端包 gzip 后多大？ | 为一个小功能引入 200KB → 自己写 |
| 依赖链 | 会带进来多少传递依赖？ | 引入 30 个包解决 1 个问题 → 换方案 |
| 安全 | `npm audit` / `pip-audit` 是否干净？ | 有未修复的高危漏洞 → 不用 |
| 可替换性 | 封装层是否隔离？ | 直接在全项目 import → 先包一层适配器 |
| 与现有栈冲突 | 版本 / 构建工具是否兼容？ | 需要降级核心依赖 → 放弃 |

引入后要做的事：

1. 在 `docs/adr/` 记一条"为什么选它、备选是什么、什么时候该换"；
2. 前端封一层（`src/api` 或 `composables`），别让 20 个组件直接 import 第三方；
3. 锁版本（`pnpm-lock.yaml` / `uv.lock` 随代码提交）。

## 3. 决策树

```
要做一件事
  │
  ├─ 仓库里已有？ ──是──▶ 直接用 / 小幅扩展（优先扩展，不要复制）
  │
  ├─ 标准库 / 框架内置能覆盖？ ──是──▶ 用它（Intl、pathlib、Pydantic、useFetch）
  │
  ├─ 已装依赖能覆盖 80%？ ──是──▶ 用依赖 + 少量适配代码
  │
  ├─ 社区有成熟库？（过三硬指标） ──是──▶ 引入 + 封一层 + 写 ADR
  │
  └─ 都没有 ──▶ 自己写，但：
                 · 放在正确的层（service / shared / utils）
                 · 写单元测试
                 · 写 README 或 docstring 说明边界
                 · 如果可能成为通用能力，设计成可替换的接口
```

## 4. 什么时候必须自己写

不要为了"复用"而引入过重的依赖：

- 逻辑只有 20 行且无边界情况（如 `truncate`、`slugify`）；
- 需求高度贴合业务（如本项目的状态机、软删除规则）；
- 现成库要求改变数据模型或引入强耦合；
- 库的许可证不兼容；
- 引入成本 > 自研成本（含学习、调试、升级）。

## 5. 三个反模式

| 反模式 | 表现 | 正确做法 |
| --- | --- | --- |
| 重复实现 | 三个页面各写一套分页请求 | 抽到 `BaseRepository.paginate` / `api` 层 |
| 过度封装 | 为一个按钮包了 5 层组件 | 组件只封一层，props 直给 |
| 依赖失控 | 为了格式化日期引入 moment | 用 `Intl` 或已有 `formatDate` |

## 6. 本项目已有的"轮子"（别再造一遍）

| 能力 | 位置 | 说明 |
| --- | --- | --- |
| 统一响应 / 分页 | `app/schemas/common.py` | `ApiResponse`、`PageResult`、`PageParams` |
| 通用 CRUD | `app/repositories/base.py` | 增删改查、软删除、分页 |
| 业务异常 | `app/core/exceptions.py` | 401/403/404/409/422/503 |
| 密码与 JWT | `app/core/security.py` | bcrypt + PyJWT |
| 登录/权限依赖 | `app/api/deps.py` | `CurrentUser`、`SuperUser` |
| HTTP 客户端 | `apps/admin/src/api/client.ts` | 拦截器、解包、401 跳转 |
| 登录态 | `apps/admin/src/stores/auth.ts` | token 持久化、用户信息 |
| 日期/文本工具 | `packages/shared/src/utils/format.ts` | `formatDate`、`formatDateTime`、`fromNow`、`truncate`、`toSlug` |
| 数据获取（portal） | `apps/portal/app/composables/usePortalApi.ts` | 统一 baseURL 与解包 |
| 模型工厂 | `app/ai/llm.py` | 换供应商只改这里 |
| 质检规则 | `app/ai/graphs/content_review.py` | 确定性校验节点 |
