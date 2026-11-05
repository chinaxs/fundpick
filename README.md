# 拾贝 FundPick

**基金筛选与分析工具**：从全市场公募基金里挑出值得看的那几只。
Vue 后台管理 + Nuxt 门户 + FastAPI 服务，pnpm workspace 组成 monorepo，数据库 MySQL。

## 有什么

- **筛选排行**：28,277 只公募基金，按区间收益、最大回撤、夏普比率、规模多维度筛选排序
- **基金详情**：净值曲线（6 档时间区间）、区间指标、公司与经理信息
- **我的关注**：注册后可收藏基金，随时回来对比
- **市场概览**：正收益占比、类型分化、收益分布等聚合数据

数据口径为 T+1 官方净值。公募基金没有实时净值，盘中估值是持仓倒推的模拟值——本站不把它包装成实时。
详见 [基金模块文档](docs/fund-module.md)。

## 技术栈

| 模块 | 目录 | 技术 |
| --- | --- | --- |
| 后台管理 | `apps/admin` | Vue 3.5 · Vite 8 · TypeScript · Element Plus · Pinia · Vue Router |
| 门户网站 | `apps/portal` | Nuxt 4 · SSR · TypeScript（SEO 友好） |
| 后端服务 | `services/api` | FastAPI · SQLAlchemy 2.x（异步）· Alembic · Pydantic v2 |
| 共享层 | `packages/shared` | 前后端共用的类型定义、常量、工具函数 |
| 数据接入 | `services/api/app/datasources` | 数据源抽象（当前 AkShare，可替换） |
| 数据库 | MySQL | 库名 `test_study`，utf8mb4 |

## 目录结构

```
project_study/
├── apps/
│   ├── admin/                  # 后台管理（SPA，端口 5174）
│   │   ├── src/
│   │   │   ├── api/            # 接口封装（axios 实例 + 模块）
│   │   │   ├── layouts/        # 布局（侧边栏 + 顶栏）
│   │   │   ├── router/         # 路由与守卫
│   │   │   ├── stores/         # Pinia 状态
│   │   │   ├── styles/         # 全局样式与设计变量
│   │   │   ├── views/          # 页面
│   │   │   ├── App.vue
│   │   │   └── main.ts
│   │   ├── vite.config.ts
│   │   └── package.json
│   └── portal/                 # 门户网站（SSR，端口 3000）
│       ├── app/
│       │   ├── components/     # 组件（Header / Footer / 文章卡片）
│       │   ├── composables/    # 数据获取封装
│       │   ├── layouts/        # 布局
│       │   ├── pages/          # 路由页面（文件路由）
│       │   ├── assets/css/
│       │   ├── app.vue
│       │   └── error.vue
│       ├── nuxt.config.ts
│       └── package.json
├── packages/
│   └── shared/                 # @project/shared
│       └── src/
│           ├── types/          # 与后端 schema 对齐的接口类型
│           ├── constants/      # 常量、字典、存储键
│           └── utils/          # 纯函数工具
├── services/
│   └── api/                    # FastAPI
│       ├── app/
│       │   ├── api/v1/             # 路由：portal（门户·匿名）/ admin（后台·登录）/ common（探活）
│       │   ├── core/               # 配置、安全、日志、异常
│       │   ├── db/                 # 引擎、会话、ORM 基类
│       │   ├── models/             # SQLAlchemy 模型
│       │   ├── schemas/            # Pydantic 模型
│       │   ├── repositories/       # 数据访问层
│       │   ├── services/           # 业务逻辑层
│       │   └── main.py
│       ├── alembic/                # 数据库迁移
│       ├── tests/
│       ├── pyproject.toml
│       └── Makefile
├── docs/                       # 架构 / 规范文档
├── pnpm-workspace.yaml
└── package.json
```

## 快速开始

前置要求：Node ≥ 22.18、pnpm ≥ 9、Python ≥ 3.12、uv、MySQL ≥ 8。

```bash
# 1. 安装前端依赖（会自动链接 workspace 包）
pnpm install

# 2. 构建共享包（apps 依赖它的产物）
pnpm build:shared

# 3. 配置后端环境变量
cp services/api/.env.example services/api/.env   # 按需修改 MySQL 账号密码

# 4. 安装后端依赖 + 初始化数据库
cd services/api
uv sync
make migrate     # 执行迁移建表
make seed        # 写入管理员账号与示例文章
cd ../..

# 5. 启动
pnpm dev         # 同时启动 admin(5174) + portal(3000)
# 或分别启动
pnpm dev:admin
pnpm dev:portal
pnpm dev:api     # FastAPI: 8000
```

访问：

- 后台管理：<http://localhost:5174>（初始账号 `admin` / `Admin@123456`）
- 门户网站：<http://localhost:3000>
- 门户接口文档：<http://127.0.0.1:8000/docs/portal>（9 个路径，匿名可访问）
- 后台接口文档：<http://127.0.0.1:8000/docs/admin>（13 个路径，需登录）
- 全量接口文档：<http://127.0.0.1:8000/docs>（24 个路径，排查跨端问题时用）

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `pnpm dev` | 并行启动两个前端 |
| `pnpm dev:api` | 启动 FastAPI（热重载） |
| `pnpm build` | 按依赖顺序构建全部前端 |
| `pnpm lint` / `pnpm type-check` | 代码检查 / 类型检查 |
| `pnpm format` | 全仓格式化 |
| `cd services/api && make dev` | 后端开发服务器 |
| `make revision m="说明"` | 生成 Alembic 迁移 |
| `make test` | 后端测试 |

## 约定

- **接口统一响应**：`{ code, message, data, request_id }`，`code=0` 为成功。详见 [docs/api.md](docs/api.md)。
- **鉴权**：JWT Bearer，access token 放 `Authorization` 头；401 由前端拦截器统一跳登录。
- **分页**：统一 `page` / `page_size`，返回 `{ items, total, page, page_size }`。
- **分层**：`router → service → repository → model`，路由不写业务逻辑，仓储不写业务规则。
- **类型共享**：后端改 schema 时同步 `packages/shared/src/types/api.ts`。

## 文档导航

**动手写代码前，建议按这个顺序读：**

| 文档 | 什么时候看 |
| --- | --- |
| [基金模块](docs/fund-module.md) | 理解基金数据模型、采集链路、接口与页面 |
| [代码规范](docs/CONVENTIONS.md) | 写第一行业务代码之前（含分层规则、评审清单、屎山预警） |
| [模块地图](docs/MODULES.md) | 不确定功能该放哪儿时 |
| [复用优先](docs/REUSE.md) | 准备造轮子/引第三方库之前 |
| [架构说明](docs/architecture.md) | 想理解整体数据流 |
| [接口约定](docs/api.md) | 前后端联调、改契约 |
| [开发规范](docs/development.md) | 新增模块/页面、迁移、提交规范 |
| [AI 能力](docs/ai.md) | 接入大模型、加工具、加工作流 |
| [架构决策](docs/adr/) | 想质疑"为什么这么选" |

**每个模块目录下都有 README**，说明职责边界与扩展方式，例如：

- 后端：[api](services/api/app/api/README.md) · [services](services/api/app/services/README.md) · [repositories](services/api/app/repositories/README.md) · [models](services/api/app/models/README.md) · [schemas](services/api/app/schemas/README.md) · [core](services/api/app/core/README.md) · [db](services/api/app/db/README.md) · [ai](services/api/app/ai/README.md) · [alembic](services/api/alembic/README.md)
- 后台：[api](apps/admin/src/api/README.md) · [stores](apps/admin/src/stores/README.md) · [views](apps/admin/src/views/README.md) · [layouts](apps/admin/src/layouts/README.md) · [router](apps/admin/src/router/README.md) · [styles](apps/admin/src/styles/README.md)
- 门户：[pages](apps/portal/app/pages/README.md) · [components](apps/portal/app/components/README.md) · [composables](apps/portal/app/composables/README.md)
- 共享：[shared](packages/shared/src/README.md)

## AI 能力（预留）

服务端已预置 LangChain / LangGraph / deepagents 三层能力，默认关闭，不影响启动：

```bash
# services/api/.env
AI_ENABLED=true
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1   # 任意 OpenAI 兼容端点
AI_MODEL=deepseek-chat
```

- 智能体对话：`POST /api/v1/admin/ai/chat`（内容助手，可查文章、给选题建议）
- 确定性工作流：`POST /api/v1/admin/ai/review`（规则校验 + 模型建议）
- 状态查询：`GET /api/v1/admin/ai/status`

设计原则、加工具/加流程的方法见 [docs/ai.md](docs/ai.md)。
