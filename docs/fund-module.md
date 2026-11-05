# 基金模块（fund domain）

第一期实现的完整业务域：**全市场基金筛选与排行**。本文说明数据模型、采集链路、接口与页面，以及已知限制。

## 1. 数据模型

| 表 | 作用 | 量级 |
| --- | --- | --- |
| `fund_companies` | 基金公司 | 215 行 |
| `fund_managers` | 基金经理（含所属公司、从业年限、管理规模） | 4231 行 |
| `funds` | 基金主数据（代码、名称、类型、风险等级、最新净值冗余字段） | 28277 行 |
| `fund_navs` | 净值序列（唯一索引 `fund_id + nav_date`） | 按需采集 |
| `fund_metrics` | 区间指标（收益、回撤、波动、夏普、排名），唯一键 `fund_id + period` | 16.9 万行 |
| `fund_sectors` | 板块归属（**第二期启用**，需季报持仓推算） | 空 |

设计要点：

- **`latest_nav` 冗余在 funds 表**：列表页要展示最新净值，每次 JOIN 净值表取最新一条代价太高。
- **指标单独成表**：列表页按"近一年收益"排序 2.8 万只基金，实时算会拖垮数据库；预计算 + 索引（`period, return_rate`）后查询退化为一次排序。
- **软删除**：`funds` 带 `deleted_at`，退市基金不物理删除，保留历史可追溯。

## 2. 数据采集

```bash
cd services/api

# 基础数据（公司/基金/经理/排行快照）——约 1 分钟
uv run python -m scripts.sync_funds --mode quick

# 风险指标（逐只请求，约 0.3 秒/只）——可分批、可重复执行
uv run python -m scripts.sync_funds --mode risk --limit 600
uv run python -m scripts.sync_funds --mode risk          # 全量约 2 小时

# 规模 / 成立日期（批量接口，约 7000 只）
uv run python -m scripts.sync_funds --mode scale

# 单只档案（全称、规模、成立日期）——按收益降序补头部，约 0.36 秒/只
uv run python -m scripts.sync_funds --mode detail --limit 500
uv run python -m scripts.sync_funds --mode detail          # 全量约 2 小时

# 净值序列（详情页曲线用）——通常无需手动跑
uv run python -m scripts.sync_funds --mode navs --limit 100
```

**净值按需回填**：访问某个基金详情页时，如果本地没有净值序列，接口会实时拉取一次并入库
（`FundService.ensure_navs`）。全市场预拉 1000 万行不划算，按访问触发更经济。

采集链路：

```
AkShareProvider.list_funds()      → funds（代码/名称/类型）
AkShareProvider.list_snapshots()  → funds（最新净值/费率）+ fund_metrics（区间收益）
fund_manager_em                   → fund_managers + funds.manager_id
fund_aum_em                       → fund_companies
经理所属公司  ──匹配──▶  funds.company_id
AkShareProvider.risk_metrics()    → fund_metrics（1y/3y/5y 的回撤/波动/夏普）
```

**数据源是可替换的**：业务代码只依赖 `app/datasources/base.py` 的 `FundDataProvider` 协议，
换持牌数据源时只新增一个实现类。原因与风险见 [ADR-0006](adr/0006-fund-data-source.md)。

### 踩过的坑（改代码时注意）

1. **pandas 的 `NaT` 是 `datetime` 子类**，必须先按字符串判空，否则会原样传给 MySQL 报 `Incorrect date value`。
2. **NaN 不能入库**：`float('nan')` 传给 asyncmy 会报 `nan can not be used with MySQL`，统一用 `to_num()` 清洗。
3. **唯一约束遇 NULL 失效**：`(name, company_id)` 在 `company_id` 为 NULL 时允许多条，导致经理被重复插入。改为按 name 做"存在则更新"。
4. **公司名称口径不一致**：公司表是"华夏基金管理有限公司"，经理表是"华夏基金"，需要前缀匹配。
5. **`on_duplicate_key_update` 不接受空字典**：只插入不更新的表（公司）要用 `INSERT IGNORE`。

## 3. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/portal/funds` | 筛选排行：`keyword` / `type` / `risk_level` / `company_id` / `period` / `sort_by` / `sort_order` / 分页 |
| GET | `/api/v1/portal/funds/filters` | 筛选项字典（类型、风险、公司、区间、排序字段） |
| GET | `/api/v1/portal/funds/{code}` | 详情（含公司、经理、费率） |
| GET | `/api/v1/portal/funds/{code}/metrics` | 各区县指标 |
| GET | `/api/v1/portal/funds/{code}/navs?limit=` | 净值序列 |
| GET | `/api/v1/admin/funds` | 后台列表（需登录） |
| GET | `/api/v1/admin/funds/sync-status` | 数据新鲜度（总数、净值行数、最新净值日） |

排序字段走**白名单枚举**（`FundSortBy`），不接受前端传字段名，避免 SQL 注入。
排序统一 `NULL` 后置，避免"没数据的基金"占据榜首。

## 4. 页面

| 端 | 路由 | 内容 |
| --- | --- | --- |
| 门户 | `/` | 市场概览：基金总数、类型入口、三个榜单、最新研报 |
| 门户 | `/funds` | 筛选页：条件筛选 + 表格 + 分页，条件同步到 URL 可分享 |
| 门户 | `/funds/[code]` | 详情：最新净值、四个指标卡、净值曲线（SVG）、区间表现表、基本信息 |
| 后台 | `/funds` | 基金管理：同步状态、筛选、列表 |

净值曲线用**手写 SVG**（`components/FundNavChart.vue`）：需求只是"一条折线 + 面积填充"，
引入 ECharts（数百 KB）不划算。若要做多基金对比、缩放、tooltip，再换图表库。

## 5. 已知限制与后续

| 限制 | 影响 | 计划 |
| --- | --- | --- |
| 风险指标覆盖率 | 全量采集中；未覆盖的基金按夏普/回撤排序时为 NULL | `--mode risk` 支持断点续跑 |
| 规模/成立日期 | 批量接口覆盖约 7000 只，其余靠 `--mode detail` 逐只补 | 全量约 2 小时 |
| 板块标签未实现 | 无法按"医药/科技"筛基金 | 第二期：季报持仓 → 行业映射 → `fund_sectors` |
| 无盘中估值 / 场内实时 | 用户看到的只有 T-1 净值 | 第三期：ETF 实时行情 + 估值接口（需注明"估算，仅供参考"） |
| 无自选与组合 | 用户不能收藏、不能算持仓收益 | 第三期：需用户体系改造（当前用户表未区分前台/后台） |
| 采集是脚本，非调度 | 需手动或外部 cron 触发 | 加 APScheduler 或独立 worker + 任务表（记录每次采集状态） |
| 数据源不可商用 | 商业发布前必须换源 | 见 [ADR-0006](adr/0006-fund-data-source.md) |

## 6. 相关文档

- 模块归属与扩展方式：[MODULES.md](MODULES.md)
- 分层与命名规范：[CONVENTIONS.md](CONVENTIONS.md)
- 数据源决策与合规风险：[ADR-0006](adr/0006-fund-data-source.md)
