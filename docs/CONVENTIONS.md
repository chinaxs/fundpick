# 代码规范（CONVENTIONS）

> 这份文档是硬约束，不是建议。`lint` / `type-check` / CI 能拦住的靠工具，工具拦不住的靠 review 和这份文档。
> 新增模块前请先读 [MODULES.md](MODULES.md) 和 [REUSE.md](REUSE.md)。

## 0. 三条底线

1. **不重复造轮子**：写之前先搜——仓库里是否已有？社区是否已有成熟实现？（流程见 [REUSE.md](REUSE.md)）
2. **依赖单向**：模块只能依赖"更内层"的模块，禁止反向和环状依赖（见第 2 节）。
3. **一个模块一个职责**：模块要能用一句话说清"我负责什么"，说不清就是拆得不对。

## 1. 总原则

| 原则 | 具体含义 | 反例 |
| --- | --- | --- |
| 单一职责 | 一个文件只做一件事；一个函数只做一层判断 | `user_service.py` 里同时写发邮件、算积分、生成报表 |
| 显式依赖 | 依赖通过参数/注入传入，不在函数内部 `import` 具体实现或 new 全局对象 | 在 service 里直接 `new HttpClient()` |
| 边界清晰 | 跨模块只通过公开接口（`__init__.py` / `index.ts` 导出）交互 | 直接 import 别的模块的私有文件 `from app.services.user import _hash` |
| 可读优先 | 变量名说人话，嵌套不超过 3 层，函数尽量 ≤ 50 行 | 用 `d = {...}` 这种缩写承载 20 个字段 |
| 失败显式 | 错误要抛出来，不要吞掉返回 `None` | `except Exception: pass` |

## 2. 模块边界与依赖方向

### 2.1 后端（FastAPI）

```
                    ┌─────────────┐
                    │   api/v1    │  路由：参数解析、鉴权、响应包装
                    └──────┬──────┘
                           │ 只能向下
                    ┌──────▼──────┐
                    │  services   │  业务规则、事务边界
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ repositories│  只写查询，不写业务判断
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   models    │  SQLAlchemy 表结构
                    └─────────────┘

    旁路（可被任意层引用，但不得反向依赖业务层）：
    core/（配置·安全·日志·异常）   db/（引擎·基类）   schemas/（Pydantic 契约）   utils/（纯函数）
    ai/（智能体与工具，见第 6 节）
```

**硬性规则**

- `api/v1` **禁止**出现 `select(...)`、`session.commit()`、业务分支判断。
- `services` **禁止**出现 `Request`、`HTTPException`、`status_code` 等 HTTP 概念；业务错误统一抛 `AppException` 子类。
- `repositories` **禁止**抛 HTTP 异常；只返回模型或 `None`。
- 路由按调用方分包：`portal/`（匿名只读）、`admin/`（需登录）、`common/`（探活）。
  `portal/` 的公开接口出现写操作（会员专属接口如 `favorites` 除外，需在 tag 标明登录）、
  `admin/` 出现无鉴权端点，视为设计错误。
- `/admin/**` 的鉴权依赖**必须**用 `StaffUser` / `SuperUser`（staff_users 表），
  不能用 `CurrentUser`（users 表，门户会员）：两边令牌 scope 不同，
  门户令牌调后台会在依赖层被拒
  （见 [ADR-0010](adr/0010-split-staff-users-table.md)）。
- `models` **禁止**写任何业务方法（可以有 `__repr__`、简单 property）。
- 跨模块复用逻辑 → 抽到 `services`，不要在路由里 import 另一个路由的函数。

**事务边界**：`commit` 只在 service 层调用，一个业务动作一次提交；`get_session` 依赖只负责异常回滚。

### 2.2 前端（admin / portal）

```
views / pages        页面：只做交互与展示，不写请求细节
      │
      ▼
api / composables    数据获取与解包，唯一允许出现 URL 的地方
      │
      ▼
stores               跨页面共享状态（登录态、UI 状态）
      │
      ▼
shared（包）          类型、常量、纯函数，零框架依赖
```

**硬性规则**

- 页面组件**禁止**直接 `axios` / `$fetch`，必须走 `src/api` 或 `composables`。
- `shared` **禁止**依赖 `vue` / `nuxt` / 任何框架，也**禁止**包含副作用（不发请求、不读 localStorage）。
- 组件超过 **200 行**必须拆；拆的依据是"职责"，不是行数硬切。
- 页面级状态放页面内（`ref`），跨页面才进 store。**不要把所有东西塞进 store**。

### 2.3 依赖方向检查清单

新增 import 前问自己：

- [ ] 我依赖的模块是否在我"下游"？（前端：页面→api→shared；后端：路由→服务→仓储→模型）
- [ ] 是否形成了环？（A→B→A 一定要拆出公共层）
- [ ] 这个依赖是否只是为了图省事（"我直接查库快一点"）？如果是，停。

## 3. 后端规范

### 3.1 命名

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| 模块文件 | 单数、小写下划线 | `user.py` `article.py` |
| 类 | PascalCase | `UserService` `ArticleRepository` |
| 函数/变量 | snake_case，动词开头 | `get_or_404` `list_published` |
| 常量 | UPPER_SNAKE | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Pydantic 模型 | 动作后缀：`XxxCreate/Update/Read/Query` | `ArticleCreate` |

### 3.2 异步

- 全部 I/O 用 `async`；**禁止**在 async 函数里调用阻塞库（`requests`、`time.sleep`、同步 db 驱动）。
- 需要跑阻塞任务用 `await asyncio.to_thread(...)` 或丢进后台任务。
- 不要在循环里逐条查库（N+1），用 `selectinload` / 一次 `IN` 查询。

### 3.3 异常

```python
# 正确：业务语义明确，由全局 handler 转成统一响应
raise NotFoundError("文章不存在")

# 错误：路由里直接抛 HTTPException（层级越界）
raise HTTPException(status_code=404, detail="not found")
```

新增错误类型时继承 `AppException`，并分配新的 `code`（见 `app/core/exceptions.py`），**不要复用**已有 code。

### 3.4 日志

- 用 `get_logger(__name__)`，不要 `print`。
- 记录"发生了什么 + 关键标识"（user_id、article_id、request_id），不要打印整个对象。
- **禁止**在日志里输出密码、token、完整身份证/手机号。

### 3.5 数据库

- 表结构只能通过 Alembic 变更，禁止手改库。
- 新增模型必须在 `app/models/__init__.py` 导出（否则 autogenerate 扫不到）。
- 软删除模型查询默认过滤 `deleted_at IS NULL`（`BaseRepository` 已处理）。
- 列表接口必须分页，`page_size` 上限 100。

### 3.6 接口契约

- 所有接口返回 `ApiResponse[T]`，`code=0` 表示成功。
- 路径：`/api/v1/{admin|portal}/{resource}`，后台与门户分开，权限不同。
- 破坏性变更（删字段、改类型）必须升 `v2` 或提供兼容期。

## 4. 前端规范

### 4.1 组件

- 文件名 PascalCase（`ArticleCard.vue`），页面用 `XxxView.vue` / Nuxt 用路由约定名。
- `props` 必须声明类型；`defineProps<{...}>()` 优于运行时声明。
- **禁止**在子组件里改 props；需要双向绑定时用 `defineModel`。
- 组件内不写业务规则（如"已发布才能删除"），规则放 `api` 层或后端。

### 4.2 状态

- 页面局部状态：`ref` / `reactive`，不放 store。
- 跨页面共享：Pinia store，按领域建（`auth`、`app`），不建"万能 store"。
- 派生数据用 `computed`，不要 `watch` 里手动同步两个变量。

### 4.3 样式

- 颜色、间距、圆角一律取 `styles/variables.scss` 中的变量，禁止散落魔法值。
- 组件样式默认 `scoped`；覆盖 Element Plus 用 `:deep()`，不要写全局选择器。
- 断点统一：`768px`（平板）/ `1024px`（桌面）。

### 4.4 请求与错误

- 请求集中在 `src/api/index.ts`（按模块分组），页面只调用函数。
- 错误提示由 `client.ts` 拦截器统一处理，页面只在需要"业务降级"时额外 catch。
- 加载态、空态、错误态三态必须处理，不能只写成功路径。

## 5. 文档规范

**每个模块目录必须有 `README.md`**，模板：

```markdown
# 模块名

一句话职责。

## 边界
- 负责：...
- 不负责：...

## 关键文件
| 文件 | 作用 |

## 扩展方式
新增 X 时改这里，不要改 Y。

## 依赖
上游 / 下游。
```

除此之外：

- 公共函数必须有 docstring（说明参数、返回值、副作用）。
- 非显而易见的决策写进 `docs/adr/`（为什么不用 A 而用 B）。
- 改了接口 → 同步 `docs/api.md` 和 `packages/shared/src/types/api.ts`。

## 6. AI 模块专规

AI 能力独立在 `services/api/app/ai/`，**不侵入**业务分层：

```
ai/
├── llm.py          模型工厂（OpenAI 兼容端点，可换模型供应商）
├── tools/          工具：把 service 能力暴露给智能体（只读优先）
├── agents/         deepagents 智能体定义（系统提示词 + 工具集）
├── graphs/         LangGraph 显式流程（多步、可中断、需人工确认的场景）
└── schemas.py      AI 接口的请求/响应模型
```

规则：

1. **工具层只调用 service，不直接查库**，保证权限、事务、软删除规则一致。
2. 写操作类工具默认 `require_confirmation=True`，且必须有审计日志。
3. 提示词与工具清单版本化（随代码提交），禁止把 prompt 散落在业务代码里。
4. 模型调用必须可降级：未配置 API Key 时接口返回明确错误（503/配置提示），不能让服务启动失败。
5. 涉及用户数据的上下文要脱敏后再送模型。
6. 智能体不做"最终裁决"：涉及金额、权限、删除的动作必须回到确定性代码路径。

## 7. 提交与评审

提交信息遵循 Conventional Commits（`feat` / `fix` / `docs` / `refactor` / `test` / `chore`），已由 commitlint + husky 强制。

**PR 自检清单**（复制到 PR 描述里逐条打勾）：

- [ ] 依赖方向没有反向/环状
- [ ] 没有重复实现已有能力（搜过 `packages/shared`、`services`、社区库）
- [ ] 新增模块有 README，新增公共函数有 docstring
- [ ] 接口变更同步了 shared 类型与 `docs/api.md`
- [ ] 数据库变更走 Alembic，且 review 过生成脚本
- [ ] 三态（加载/空/错误）都有处理
- [ ] 日志不含敏感信息
- [ ] `pnpm lint && pnpm type-check`、`make lint && make test` 通过

## 8. 屎山预警信号

出现以下任一情况，立即停下来重构，不要"先跑通再说"：

1. 一个文件超过 400 行，或一个函数超过 80 行。
2. 出现 `utils.py` 成了垃圾桶（里面塞了 20 个不相关函数）。
3. 两个模块互相 import。
4. 为了加一个字段，改了 5 个以上文件。
5. 业务判断开始出现在 `api/v1` 或 `.vue` 模板里。
6. 同一段逻辑在 3 处以上复制粘贴（第 3 次就该抽象）。
7. 没人能说清某个模块"为什么存在"。
8. 改 A 功能导致 B 功能坏掉（缺少边界测试）。
