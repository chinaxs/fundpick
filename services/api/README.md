# FundPick API｜基金模拟交易与持仓管理

FastAPI + SQLAlchemy异步 + Alembic + MySQL。完整安装步骤以[根目录README](../../README.md#快速开始)为准。

```bash
# 在根目录运行pnpm setup:dev并准备数据库后
uv sync --frozen
make migrate
make seed   # 设置自己的后台管理员密码；不提供默认密码
make dev
```

默认只创建`staff_users`中的后台管理员，不创建门户会员或虚构基金。无人值守使用环境变量`INITIAL_ADMIN_PASSWORD`；`--demo-content`按需创建明确标记的演示草稿。重复初始化不重置账号、提升权限或恢复被禁用账号。

- API：`app/api/v1`，按portal/admin/common划分。
- 服务/仓储/模型：`app/services`、`app/repositories`、`app/models`。
- 数据接入：`app/datasources`、`scripts/sync_funds.py`。
- 数据库迁移：`alembic/versions`，新增模型须在`app/models/__init__.py`导出。
- 初始化：`scripts/seed.py`；独立测试数据：`scripts/seed_test_data.py`。

事务提交由服务层处理；路由负责参数与权限，仓储负责查询。后台与门户账号独立，接口变更同步`packages/shared`。

```bash
make lint
make typecheck
# make test前先按docs/testing.md配置独立测试库
```

[交易规则](../../docs/trading-flow.md) · [独立测试](../../docs/testing.md) · [部署](../../docs/deployment.md) · [MIT许可](../../LICENSE)
