# 参与贡献 / Contributing

欢迎改进基金模拟交易、持仓管理、基金筛选、数据质量和使用体验。提交前请先阅读[开发规范](docs/development.md)与[模块地图](docs/MODULES.md)。

## 本地开发

按照[README](README.md#快速开始)安装。AI默认关闭，普通基金与记账功能不要求配置模型密钥。请使用自己的开发数据库；回归测试必须使用**独立测试库**，不要将测试数据写入日常使用的账本库。

```bash
pnpm build:shared
pnpm type-check
pnpm build
node apps/portal/scripts/acceptance-flow-form.mjs
cd services/api
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts/seed.py
# 按docs/testing.md配置独立数据库后再运行pytest
```

## 提交与Pull Request

1. 新建`feat/功能名`或`fix/问题名`分支。
2. 保持改动集中，说明触发条件、改动后的行为及验证方法。界面修改可附脱敏截图。
3. 涉及数据库时提交Alembic迁移；接口变化同步共享类型。
4. 提交信息使用Conventional Commits，例如`fix(api): 校验历史卖出份额`。

新增测试应检查真实业务约束：净值日期准确、份额不透支、费用有来源、转换资金守恒、账号隔离，以及重复请求不重复记账。

## Issue与安全问题

Bug反馈请包含复现步骤、版本、运行环境和脱敏日志；不要提供密码、令牌、真实持仓或数据库备份。安全漏洞请按[SECURITY.md](SECURITY.md)处理，不要在公开Issue中披露凭据。

贡献原创代码时，你同意按本项目的[MIT许可证](LICENSE)提供该贡献；第三方代码应保留适用的许可与署名。
