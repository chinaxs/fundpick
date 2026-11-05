# study-api

FastAPI + SQLAlchemy 2.x（异步）+ Alembic + MySQL。

## 快速开始

```bash
cp .env.example .env      # 修改数据库账号密码
uv sync                   # 安装依赖（含 dev）
make migrate              # 建表
make seed                 # 初始管理员 + 示例文章
make dev                  # http://127.0.0.1:8000/docs
```

## 目录

```
app/
├── api/
│   ├── deps.py             会话 / 当前用户 / 权限依赖
│   └── v1/
│       ├── router.py       路由汇总
│       └── endpoints/      health · auth · users · articles · portal
├── core/                   config · security · logging · exceptions
├── db/                     base（ORM 基类 + Mixin）· session（引擎 / 会话）
├── models/                 SQLAlchemy 模型
├── schemas/                Pydantic 模型
├── repositories/           数据访问层
├── services/               业务逻辑（事务边界）
├── utils/
└── main.py                 应用工厂 + 中间件 + 异常处理
alembic/                    迁移脚本
tests/                      pytest
scripts/seed.py             初始化数据
```

## 分层规则

`endpoints → services → repositories → models`

- 路由层只做参数解析、鉴权、响应包装。
- **事务提交在 service 层**（`await session.commit()`），依赖只负责异常回滚。
- 仓储层不抛 HTTP 异常，业务异常统一用 `app.core.exceptions` 中的类型。

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `make dev` | 热重载开发服务器 |
| `make test` | 运行测试 |
| `make lint` / `make format` | Ruff 检查 / 格式化 |
| `make typecheck` | mypy |
| `make revision m="说明"` | 生成迁移 |
| `make migrate` | 应用迁移 |
| `make seed` | 写入初始数据 |

## 环境变量

见 `.env.example`，关键项：`MYSQL_*`、`SECRET_KEY`（生产必须替换）、`CORS_ORIGINS`、`ACCESS_TOKEN_EXPIRE_MINUTES`。

## 注意

- 连接串由 `settings.database_url` 生成，驱动为 `asyncmy`。
- 新增模型后必须在 `app/models/__init__.py` 导出，否则 Alembic autogenerate 扫不到。
- `logs/` 目录自动创建，日志按 10MB 滚动保留 5 份。
