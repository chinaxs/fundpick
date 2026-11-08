# 在独立数据库运行测试

集成测试会创建会员、基金、交易与采集任务，因此不要对日常使用的数据库运行。建议单独准备MySQL 8.4数据库，例如`fundpick_test`，并使用只对该库授权的账号。

```bash
cd services/api
export APP_ENV=test
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_DB=fundpick_test
export MYSQL_USER=fundpick_test
# 由你的环境或密钥管理工具设置MYSQL_PASSWORD，勿写入提交
export SYNC_SCHEDULER_ENABLED=false
uv run alembic upgrade head
uv run python -m scripts.seed_test_data
uv run pytest -q
```

`seed_test_data`只允许`APP_ENV=test`且库名包含`test`，会写入确定性的虚构基金与测试管理员。测试中的示例密码只用于这个隔离数据库。`pytest`默认同时收集`test_*.py`和`acceptance_*.py`。

前端验证在项目根目录执行：

```bash
pnpm install --frozen-lockfile
pnpm build:shared
pnpm type-check
pnpm build
node apps/portal/scripts/acceptance-flow-form.mjs
```

GitHub Actions会创建独立MySQL 8.4服务，执行空库迁移、测试数据初始化、管理员初始化幂等检查和完整回归。远端是否通过，以实际Actions运行结果为准。
