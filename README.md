# 拾贝 FundPick｜开源基金模拟交易与持仓管理

[![CI](https://github.com/chinaxs/fundpick/actions/workflows/ci.yml/badge.svg)](https://github.com/chinaxs/fundpick/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**基金模拟交易、投资记账、持仓管理、基金筛选与收益分析工具。** 基于 Nuxt 4、Vue 3、FastAPI 和 MySQL，可自行部署。

FundPick is an open-source, self-hosted **fund paper trading and portfolio tracker** for Chinese mutual funds. Track buy/sell records, historical NAV dates, fees and portfolio returns; screen and compare funds in one place.

[快速开始](#快速开始) · [功能介绍](#功能介绍) · [交易规则](docs/trading-flow.md) · [参与贡献](CONTRIBUTING.md) · [MIT License](LICENSE)

## 适合用来做什么

- **记录真实平台交易**：将支付宝、天天基金等平台发生的买卖记在一个账本中，统一观察持仓与收益。
- **基金模拟交易与练习**：使用真实基金净值记录模拟买卖，理解费用、确认时间和持有期收益。本站不连接交易通道，不执行真实申购、赎回或资金划转。
- **个人基金研究**：按类型、主题、区间收益、最大回撤、夏普等条件筛选基金，关注与对比候选产品。
- **二次开发**：基于前后端分离架构扩展自己的基金管理、投资复盘或个人金融工具。

## 功能介绍

| 功能 | 说明 |
| --- | --- |
| 基金筛选与对比 | 代码、名称、拼音搜索，类型/主题/风险筛选，基金详情、净值曲线与最多3只基金对比 |
| 基金模拟交易 | 买入填金额、卖出填份额，记录下单时间，自动查询对应日期净值与可用费率 |
| 持仓管理与收益 | 加仓、卖出、已清仓记录，持仓成本、市值、持有收益和累计收益 |
| 交易流水 | 按基金名称/代码、方向、状态和日期筛选，分页、撤销、纠错作废与删除 |
| 更多持仓操作 | 添加已有持仓、现金分红、红利再投、拆分和基金转换，按需展开 |
| 自选基金与工作台 | 关注、持仓标记、工作台概览与快捷买入入口 |
| 行情与资讯 | 指数行情、分时/K线，公开资讯来源、数据时间与延迟提示 |
| 运营后台 | 基金数据采集、任务进度、数据质量、会员支持、内容版本与操作审计 |
| AI扩展基础 | 保留数据来源、确认状态与修正链；内容助手默认关闭，普通功能无需模型密钥 |

### 模拟交易的数据规则

“模拟”表示不执行实际交易，日期和数据仍需要认真处理：

- 普通境内开放式基金按**北京时间15:00**与证券交易日历判断净值所属日；15:00整及以后顺延。
- 周末、节假日与未知日历范围分别处理，不拿“最近公布的净值”替代应有日期的净值。
- 净值或费率尚未取得时保留待处理，正常等待后自动入账；自动计算不会冒充已与平台对账。
- 实际平台费用、份额和到账结果可以按平台信息核对；未知费用不自动填成零。
- 转换保留转出、转入两侧份额与金额，校验资金守恒和后续持仓，避免超卖和重复记账。

详见[交易流程与边界](docs/trading-flow.md)。自动结果可能与平台折扣或确认精度不同，以平台实际结果为准。

## 快速开始

要求：Node.js 22.21+（推荐`.nvmrc`版本）、pnpm 9、Python 3.12+、[uv](https://docs.astral.sh/uv/)。下面使用Docker Compose启动独立MySQL 8.4，也可以接入自己准备的MySQL。

### 1. 安装依赖并生成本地配置

克隆本仓库并进入项目根目录：

```bash
git clone https://github.com/chinaxs/fundpick.git
cd fundpick
nvm use  # 使用nvm时；否则自行安装.nvmrc指定的Node版本
pnpm install --frozen-lockfile
pnpm setup:dev
```

`setup:dev`生成根目录`.env`与`services/api/.env`，包含随机数据库密码和JWT签名密钥，默认数据库为`fundpick`、端口为`3307`。文件不会进入Git，密钥不会输出到终端；已有配置时会停止，避免覆盖你的环境。

已有MySQL时，可手动复制`services/api/.env.example`为`.env`，填写已创建的专用账号、空数据库、真实密码和随机`SECRET_KEY`，直接跳到第3步。不要用`root`运行应用；`scripts/init_db.sql`只负责建库，不含固定账号密码。

### 2. 启动开发数据库

```bash
docker compose -f compose.dev.yml up -d --wait
```

此配置只启动本机开发数据库并保留数据卷，不启动API或前端。正式部署参考[部署说明](docs/deployment.md)，不要将开发配置直接暴露到公网。

### 3. 迁移并初始化管理员

```bash
pnpm build:shared
cd services/api
uv sync --frozen
make migrate
make seed
```

`make seed`交互要求你设置管理员密码，不回显、不写日志，**没有默认管理员密码**。默认用户名为`admin`；重复运行会保留已有账号的密码和权限。无人值守部署可通过环境变量`INITIAL_ADMIN_USERNAME`和`INITIAL_ADMIN_PASSWORD`传入，不要把真实值写入公开命令示例或Git。

默认不会创建虚构基金、测试会员或新闻。需要一篇明确标注的演示草稿时，可运行`uv run python -m scripts.seed --demo-content`。

### 4. 启动API和前端

在第一个终端，保持位于`services/api`：

```bash
make dev
```

在第二个终端，回到项目根目录：

```bash
pnpm dev
```

| 服务 | 地址 |
| --- | --- |
| 官网与基金工作台 | http://localhost:3000 |
| 管理后台 | http://localhost:5174 |
| 后端API文档 | http://127.0.0.1:8000/docs |
| 门户API文档 | http://127.0.0.1:8000/docs/portal |
| 后台API文档 | http://127.0.0.1:8000/docs/admin |

后台使用刚设置的账号密码；官网会员独立注册，两套账号互不通用。

### 5. 导入公开基金数据

首次安装是空数据库。后台登录后进入“采集监控”，按需启动基础数据同步，或执行：

```bash
cd services/api
uv run python -m scripts.sync_funds --mode quick
```

数据量、接口可用性和采集耗时取决于上游，不附带整库行情。请遵守来源站的访问限制。风险指标、历史净值等采集模式见[基金模块](docs/fund-module.md)。

## 技术与目录

```text
apps/portal/       Nuxt 4官网：基金筛选、模拟交易、工作台
apps/admin/        Vue 3 + Element Plus管理后台
services/api/      FastAPI + SQLAlchemy异步API、采集与Alembic迁移
packages/shared/   TypeScript共享类型、常量和工具
scripts/           开发配置与发布检查
.github/workflows/ 独立数据库CI
```

| 操作 | 命令 |
| --- | --- |
| 两个前端开发服务 | `pnpm dev` |
| 后端热重载 | `pnpm dev:api` |
| 类型检查 | `pnpm type-check` |
| 生产构建 | `pnpm build` |
| 后端质量检查 | `cd services/api && make lint && make typecheck` |
| 密钥与历史检查 | `python3 scripts/check-secrets.py --history` |

集成测试会写数据，**请使用独立测试库**，不要在正在使用的持仓数据库上运行。步骤见[测试说明](docs/testing.md)。

## 数据、隐私与已知限制

- 本项目不提供基金交易执行，不推荐买卖具体产品、不承诺收益；历史表现不代表未来结果。
- 公开数据可能延迟、缺失或变更。特殊基金及平台规则不能一律套用15:00规则，页面保留来源与待核对状态。
- 代码开源许可不包含上游基金数据、行情或资讯的再分发授权。部署及商业用途需单独确认来源条件，见[数据源说明](docs/adr/0006-fund-data-source.md)。
- 只发布代码与必要示例，不发布真实会员、交易记录、会话、日志、API密钥或数据库备份。
- 当前为早期版本。生产环境真实备份恢复演练尚未完成，部署者需要自行验证，见[版本记录](CHANGELOG.md)。

## 贡献与文档

欢迎通过Issue反馈基金模拟交易、持仓计算、基金筛选与部署问题，也欢迎提交Pull Request。请先阅读[贡献指南](CONTRIBUTING.md)；安全问题使用[安全报告渠道](SECURITY.md)。

[架构说明](docs/architecture.md) · [模块地图](docs/MODULES.md) · [交易流程](docs/trading-flow.md) · [基金模块](docs/fund-module.md) · [测试](docs/testing.md) · [部署](docs/deployment.md) · [项目代办](docs/TODO.md)

## License

FundPick原创代码采用[MIT License](LICENSE)。第三方依赖保留各自许可证；图表使用[TradingView Lightweight Charts™](https://www.tradingview.com/)，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

## 搜索关键词 / Keywords

基金、基金模拟交易、模拟买卖、基金持仓管理、投资记账、基金净值、基金筛选、收益分析、个人投资管理。

Mutual funds, fund paper trading, simulated trading, portfolio tracker, investment tracker, personal finance, self-hosted, Nuxt, Vue, FastAPI, AkShare.
