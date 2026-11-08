# 接口约定

Base URL：`http://127.0.0.1:8000/api/v1`

## 接口分组

接口按**调用方**分三组，URL 前缀即归属，看地址就能判断权限要求：

| 前缀 | 调用方 | 鉴权 | 特征 |
| --- | --- | --- | --- |
| `/portal/**` | 门户网站（浏览器 + SSR） | 无 | 匿名只读，可公开缓存 |
| `/admin/**` | 后台管理 | 必须登录，部分需超管 | 含写操作与敏感数据 |
| `/health/**` | 负载均衡、监控 | 无 | 探活，无业务逻辑 |

两个前端严格对应：

- `apps/portal` **只**调用 `/portal/**`
- `apps/admin` **只**调用 `/admin/**`

门户有自己的用户体系（注册、自选），登录入口为 `/portal/auth/**`，
与 `/admin/auth/**` 完全独立——**两张不同的表**（`users` / `staff_users`），
令牌各自带 `scope`（`portal` / `staff`），解码端强校验，两套身份互不通用：
门户令牌调 `/admin/**` 返回 401，员工令牌调 `/portal/auth/me` 同样 401。

> 新增接口时先判断"谁在调用"，再放进对应路由包：
> `app/api/v1/{portal,admin,common}/`。不要平铺在 `router.py` 里。

## 统一响应

所有业务接口返回同一结构（HTTP 状态码同时表达语义）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "9f8c1e..."
}
```

| 字段 | 说明 |
| --- | --- |
| `code` | 业务码，`0` 成功；非 0 见下表 |
| `message` | 可直接展示给用户的提示 |
| `data` | 业务数据，失败时为 `null` 或校验详情 |
| `request_id` | 与响应头 `X-Request-ID` 一致，排查问题时提供此值 |

### 业务码

| code | HTTP | 含义 |
| --- | --- | --- |
| 0 | 200/201 | 成功 |
| 40100 | 401 | 未认证 / token 失效 |
| 40300 | 403 | 无权限 |
| 40400 | 404 | 资源不存在 |
| 40900 | 409 | 冲突（用户名重复等） |
| 42200 | 422 | 参数校验失败（`data` 为字段错误列表） |
| 50000 | 500 | 服务器内部错误 |
| 50300 | 503 | 依赖能力未就绪（如 AI 未配置密钥） |

## 分页

请求参数：`page`（从 1 开始）、`page_size`（1–100）。

```json
{ "items": [], "total": 128, "page": 1, "page_size": 20 }
```

## 鉴权（后台，staff_users 表）

1. `POST /admin/auth/login`，body：`{ "username": "admin", "password": "..." }`（username 也接受邮箱）
2. 返回 `access_token`（默认 2 小时）、`refresh_token`（7 天），令牌 `scope=staff`
3. 后续请求带 `Authorization: Bearer <access_token>`
4. 过期后用 `POST /admin/auth/refresh` 换新 token
5. `GET /admin/auth/me` 获取当前员工

门户会员接口走 `/portal/auth/**`（`users` 表，令牌 `scope=portal`），两套账号互不通用。

## 接口清单

### 门户 · 会员（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/portal/auth/register` | 注册，成功后直接返回令牌（自动登录） |
| POST | `/portal/auth/login` | 登录（用户名或邮箱 + 密码） |
| POST | `/portal/auth/refresh` | 刷新令牌 |
| GET | `/portal/auth/me` | 当前会员（只含展示字段，无内部状态） |
| POST | `/portal/auth/logout` | 语义化退出；JWT 无状态，客户端丢弃令牌即可 |

**门户注册的账号不能登录后台**：账号只存在 `users` 表，后台登录（查 `staff_users`）返回 401；
即便持有有效 token（`scope=portal`），调用 `/admin/**` 也会得到 401。详见 [ADR-0009](adr/0009-portal-member-isolation.md)。

### 门户 · 自选（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/favorites` | 我的关注列表（分页，含所选区间指标） |
| GET | `/portal/favorites/codes` | 已关注代码列表，列表页标记星标用（一次拉全量，最多 500） |
| POST | `/portal/favorites` | 关注，body：`{ "code": "002910" }`；已关注时幂等 |
| DELETE | `/portal/favorites/{code}` | 取消关注 |

取消关注是**硬删除**：软删会占住 `(user_id, fund_id)` 唯一约束，导致取消后无法再次关注。

### 门户 · 会员中心（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/me/dashboard?period=1y` | 工作台聚合：关注数/平均收益/正收益占比/夏普、类型/风险/板块/收益分布、收益榜与最近关注 |
| PATCH | `/portal/me` | 更新资料：仅 `email` / `full_name` / `avatar_url`，用户名与状态不可改 |
| POST | `/portal/me/change-password` | 修改密码，校验原密码；JWT 无状态，已签发令牌继续有效至过期 |
| POST | `/portal/me/deactivate` | 注销账号：body `{password}` 二次校验 → 清空关注与持仓 → 软删用户，旧令牌立即失效 |

### 门户 · 反馈与找回密码

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/portal/feedback` | 提交反馈 `{category,title,content,contact?,page_url?}`；需登录，`category` ∈ account/data/function/bug/other |
| GET | `/portal/feedback` | 本人反馈列表（含后台回复与处理状态） |
| POST | `/portal/auth/forgot-password` | 提交重置申请 `{account}`；账号存在与否返回同一提示，避免枚举注册邮箱 |
| POST | `/portal/auth/reset-password` | `{token,new_password}`；令牌一次性、30 分钟过期，成功后撤销该账号全部会话 |

没有邮件服务，因此流程是「会员申请 → 客服核实身份 → 后台生成一次性链接 → 线下发给本人」，
不伪装"已发送邮件"。重置令牌只存 SHA-256 摘要。

### 门户 · 真实平台交易记录新增契约

申请时间 `submitted_at` 必须带时区，响应规范为北京时间；`confirmed_on` 兼容字段表示**净值所属日**，`settled_on` 为**平台确认日**。
新增 `record_source=receipt` 时须填写平台、申请时间、日期规则和实际费用；平台确认日可不填，保留 null；买入还须 `confirmed_shares`，卖出须 `received_amount`。
份额按实际回执保存而非重新折算；同平台持仓分别结转成本。`pricing_rule=cn_open` 校验普通境内场外基金15:00与已核对的交易日历；`platform` 以平台回执净值日记录，须 `date_reason`。
手填净值与本地同日净值不一致、或回执金额存在算术差异时返回 warnings 供核对，不覆盖原值。
新流水返回 `platform / submitted_at / settled_on / record_source / receipt_ref / pricing_rule / date_reason / application_id`；旧折算来源仍为 calculated。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/portal/me/transactions/timing` | `{code, submitted_at, pricing_rule}` → expected_nav_on、official_nav、日历来源和说明；未取得同日净值返回 null |
| POST | `/portal/me/applications` | `{code,kind,submitted_at,platform,pricing_rule,amount?或shares?,note?,request_key}`，只保存待确认申请 |
| GET | `/portal/me/applications` | 本人待确认清单，不影响可卖份额或已实现收益 |
| POST | `/portal/me/applications/{id}/cancel` | 移除本地待确认记录，不撤销外部平台申请 |

从申请补录回执时传 `application_id`，所属会员、基金、方向、平台和申请时间需匹配；确认与状态更新同事务；重复 request_key 不重复记账。
组合 summary 新增 `calculated_count` / `pending_count`，区分旧估算与待确认记录。仅持仓金额/收益使用有效已确认流水。
完整规则、精度和日历范围见 [trading-flow.md](trading-flow.md)。以下旧交易契约保留兼容，不再代表新门户的默认记账方式。

### 门户 · 模拟持仓与交易（需登录）

当前入口为已确认模拟交易记账，详细流程与收益口径见 [trading-flow.md](trading-flow.md)。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/me/holding-codes` | 当前会员已确认且仍有剩余份额的基金代码；不含金额，清仓、作废会同步变化 |
| GET | `/portal/me/portfolio` | `{holdings, summary, legacy_positions}`；按有效流水合并基金持仓，清仓收益保留，旧记录独立待核对 |
| POST | `/portal/me/transactions/preview` | 预览 `TradeInput`，返回份额、现金流、盈亏、剩余成本、净值来源与 `preview_hash`，不落库 |
| POST | `/portal/me/transactions` | `{request: TradeInput, preview_hash, request_key: UUID}`；重算并核对预览，幂等确认 |
| GET | `/portal/me/transactions` | 全部流水（含作废），`page/page_size` 分页，每页最多 100 |
| POST | `/portal/me/transactions/{id}/void` | `{reason}`；只允许作废同基金最后一笔有效成交，保留原记录和原因 |

`TradeInput`：`{code, kind: buy|sell, confirmed_on, nav_mode: official|manual, nav?, amount?, shares?, fee, note?, legacy_position_id?}`。
买入填写含手续费的 `amount`；卖出填写 `shares`，两者不可混填；`fee` 是费用金额而不是费率。
`official` 仅查询确认日当天净值，无数据返回 422；`manual` 必填净值，流水中注明来源。
`legacy_position_id` 仅供旧记录核对迁为买入，成功后移出待核对区，作废恢复。
确认后持仓变化用移动平均成本计算，金额保留分、模拟份额 4 位小数。
重复 `request_key` 与同内容返回原回执，改内容返回 409；预览不匹配返回 409，超卖和错误日期返回 422，越权作废返回 404。

组合 `summary` 继承 `PositionSummary`，其中 `total_amount` 表示**剩余持仓成本**，`count` 表示**持有基金只数**；
增加 `realized_profit / total_return / total_buy_amount / total_sell_amount / fees / transaction_count / legacy_count`。
持有收益 `total_profit = 总市值 − 剩余成本`，累计收益 `total_return = 持有收益 + 已实现收益`。
任一活跃持仓缺少合格净值时，市值和对应收益返回 null；已实现收益不受影响。
工作台新增 `portfolio_summary` 供新界面使用，旧 `position_summary` 保留兼容。

### 门户 · 持仓工具（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/portal/me/portfolio/import` | 历史持仓导入 `{rows:[{code,confirmed_on,shares?,amount?,nav?,platform?,note?}], dry_run?}`；份额/金额/净值至少两项。**该基金已有记录时拒绝**，避免历史记两遍 |
| GET | `/portal/me/portfolio/flows` | 分红/再投/拆分/转换流水 |
| POST | `/portal/me/portfolio/flows` | 记录公司行为 `{code,kind,effective_on,platform?,request_key?,...}`；转换用 `target_*` 描述对手基金，一次写转出+转入两条配对流水（`transfer_group`）。多平台持有且未填 `platform` 返回 422 |
| DELETE | `/portal/me/portfolio/flows/{id}` | 删除本人流水 |
| GET | `/portal/me/portfolio/reconciliation` | 收益核对：回执份额/成本 + 公司行为份额影响 + 累计投入/赎回/分红/已实现 |
| GET | `/portal/me/portfolio/export` | 导出 CSV（买卖与公司行为同一份账本，UTF-8 BOM） |
| GET | `/portal/me/portfolio/ai-context` | 账号账本快照，每条记录带 `confidence`（receipt/estimated/import/pending/legacy）与修正链 |

公司行为单独存表，不改写平台回执确认的份额：拆分、再投、转换按**归属平台**并入同一账本，
来源与确认状态始终可追溯。`platform` 为空时：只持有一个平台自动补齐，
**多个平台直接返回 422 要求选择**——"再投发生在 A 还是 B"是查不到的外部事实，
不替用户推定；历史缺归属的记录保持 `platform=null`（平台未知），不静默升级。

**转换字段口径**：`code` 是当前基金，`target_*` 是对手基金。
`cash_amount` 是**本侧毛金额**，`target_cash_amount` 是对手侧到账金额；
两者的差是转换费用/损耗，会计入已实现收益（响应里的 `net_amount` 显示转出侧实际结转净额）。
`convert_out` 时 `shares_delta` 为转出份额、`target_shares` 为转入份额；
`convert_in` 时 `shares_delta` 为转入本基金的份额、`target_shares` 为对方转出份额。
缺份额只用**本侧**金额 ÷ 净值推算；两侧都不能确定时返回 422，绝不复制另一侧份额。

**幂等与删除**：`request_key` 相同的重试返回首次结果；同一个键但内容（金额/份额/日期/平台等）
不同返回 409。删除为软删除，记录保留墓碑，旧请求重试返回 409 而不是重新入账。

**写入校验**：新增公司行为前会对全部受影响基金（转换两侧）重放整本账，
出现负份额、批次不足或成本为负时整组回滚并返回 409——补录过去的转换不能让
之后已成交的卖出变成负份额。
导入的记录 `record_source=import`，与回执/估算明确区分。

以下为旧版持仓接口，兼容期保留并在 OpenAPI 标记 deprecated；新门户只通过上述交易接口生成新持仓。

#### 旧版模拟持仓兼容接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/me/positions` | 我的模拟持仓明细（含份额、市值、浮动盈亏） |
| POST | `/portal/me/positions` | 新增，body：`{code, amount, bought_at?, note?}` —— **不接收净值** |
| PATCH | `/portal/me/positions/{id}` | 编辑金额/买入日期/备注，日期变化时自动重算净值 |
| DELETE | `/portal/me/positions/{id}` | 删除（硬删除，允许反复增删） |

**用户只录金额 + 日期，净值完全由系统查**：
按买入日期取 `fund_navs` 中「当天或之前最近一个交易日」的单位净值
（非交易日自然落到上一交易日）；本地没有该日期之前的历史净值时回退 `funds.latest_nav`，
并在 `nav_source` 标注 `latest`（明细与提交提示都会如实说明）。
份额不落库：`shares = amount / cost_nav`，改金额或日期自动重算。
估值口径：`market_value = shares × funds.latest_nav`、`profit = market_value - amount`、
`profit_rate = profit / amount × 100`。任一持仓缺少最新净值时，汇总的
`total_market_value` / `total_profit` / `profit_rate` 为 `null`，避免把缺失市值计成亏损；
`total_amount` 仍包含全部成本，`valued_count` 返回可估值笔数，单笔明细继续可查。
校验：买入日期不能是未来，也不能早于基金成立日。
同一基金允许多笔持仓（分批建仓），故不设唯一约束。所有操作按 `CurrentUser` 隔离，
`get_owned` 校验归属，越权编辑/删除返回 404。

`GET /portal/me/dashboard` 只返回 `position_summary` 概览；
明细在 `GET /portal/me/positions`（`{items, summary}`），收藏列表在 `GET /portal/favorites`，
前端对应 `/dashboard`、`/positions`、`/favorites` 三个独立页面（共用 MemberNav 二级导航）。

全部接口只作用于 `CurrentUser`（令牌 `scope=portal`），不接收 `user_id`，从设计上杜绝越权。
工作台统计一次 join 取回关注基金后在内存分组（关注数上限 500），避免 6 条 GROUP BY SQL。

### 门户 · 基金（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/funds` | 筛选排行（keyword / type / risk_level / **sector** / company_id / period / sort_by / sort_order） |
| GET | `/portal/funds/filters` | 筛选项字典（类型、风险、**板块含数量**、公司、区间、排序字段） |
| GET | `/portal/funds/compare?codes=000003,000004` | 2–3 只基金对比：费率、区间收益/回撤/夏普、净值日期；`available=false` 表示上游无该区间风险数据 |
| GET | `/portal/funds/{code}` | 基金详情（公司、经理、费率、规模） |
| GET | `/portal/funds/{code}/metrics` | 各区间指标（收益、回撤、波动、夏普、排名） |
| GET | `/portal/funds/{code}/navs` | 净值序列，支持 `period`（1m/3m/6m/1y/3y/all）与 `limit`（超限等距抽样） |
| GET | `/portal/funds/{code}/holdings` | 季度重仓股（`quarter` 缺省取最新；本地无数据时实时回填） |

`keyword` 支持四类输入，用**空格分隔多个词时是"且"的关系**（最多 4 个）：

| 输入 | 命中方式 |
| --- | --- |
| `000001`、`021180` | 基金代码 |
| `华夏成长`、`成长` | 简称 / 全称包含 |
| `huaxia`、`hxcz` | 名称全拼 / 拼音首字母（`funds.name_pinyin`、`name_initials`，由同步脚本维护） |
| `易方达` | 基金公司名称 |
| `半导体`、`新能源` | 中文板块名映射到板块 key（名里没有这个词也能命中） |

拼音列由 `scripts/sync_funds.py --mode pinyin` 回填（28k 行约 13 秒），
日常 `--mode quick` 会顺带写入新基金的拼音。`%关键词%` 用不到索引，
28k 规模下单次匹配约 90ms。

### 门户 · 统计（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/stats/overview` | 总数、公司数、类型分布与各类型平均收益 |
| GET | `/portal/stats/return-distribution` | 区间收益分布分桶（`period`，默认 `1y`） |

### 门户 · 行情（公开）

行情响应区分三个时间，不能互相替代：

| 字段 | 含义 |
| --- | --- |
| `as_of` | 本次响应的服务端时间 |
| `fetched_at` | 最近一次成功从上游抓取的时间（降级时可能是几分钟前） |
| `data_as_of` | **原始行情时间**：分时取最后一个分时点、日 K 取最后一根 K 线当日 15:00；快照上游无时间戳时为 `null` |

`degraded=true` 表示上游失败、展示的是旧缓存或空数据，`degraded_reason` 给出原因；
`calendar_known=false` 表示交易日历未覆盖当前年份，`market_status` 只是按星期估算。


| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/market/indices` | 8 个核心指数实时快照（点位、涨跌、开高低、成交额）+ 交易状态 + 行情日期 |
| GET | `/portal/market/indices/trends?days=60` | 各指数最近 N 个交易日收盘序列（5–250），供迷你走势图 |
| GET | `/portal/market/indices/{code}` | 单个指数快照（详情页首屏）。代码不在清单内返回 404，行情源无数据返回 503 |
| GET | `/portal/market/indices/{code}/intraday` | 当日分钟级分时（241 点），含昨收；上游失败返回 200 + 空序列 |
| GET | `/portal/market/indices/{code}/candles?days=250` | 日 K（开高低收 + 量额），20–2000 根，升序 |
| GET | `/portal/market/indices/stream` | **SSE 推送**：每条 `event: quotes`，data 为完整快照 |

跟踪清单固定在 `app/market_indices.py`（上证、深证、创业板、科创50、沪深300、中证500、中证1000、北证50），
**不接受前端传代码**：行情源一次返回整张表，服务端过滤即可，也避免接口变成通用行情代理。
新增指数只改这一个文件，接口与前端自动带上。

交易状态按北京时间判定：`pre_open`（<9:30）、`trading`（9:30–11:30、13:00–15:00）、
`lunch_break`（11:30–13:00）、`closed`（15:00 后与周末）。节假日当天返回 `closed` 也算符合事实。

#### 为什么用 SSE 而不是 WebSocket

行情是**只读的单向流**，SSE 走普通 HTTP，断线由浏览器自动重连，不需要协议升级、
心跳帧和双向状态机。更关键的是延迟瓶颈在上游（东财快照本身延迟数秒到十几秒），
换协议无法让数据更早产生。

服务端只启一个后台刷新任务，所有连接从同一个队列取数据——连接数涨，上游请求数不变。
多 worker 部署时每个进程各跑一份；行情是幂等的公开快照，不需要跨进程一致，
因此不必引入 Redis 广播（只有在"订阅业务事件"时才需要）。

前端策略：首屏由 SSR 拿到快照，水合后建立一条连接；若 45 秒收不到帧
（比如反向代理把流缓冲了），自动降级为 15 秒轮询，收到帧再切回推送。

#### 性能与稳定性

- 快照缓存 5 秒、走势缓存 5 分钟、分时缓存 20 秒（休市 120 秒）、上游超时 8 秒；
- 缓存过期瞬间的并发请求走**单飞**（同 key 只发一次上游请求）；
- 上游异常时回退上一次缓存；连缓存都没有则返回 200 + 空列表，
  前端显示"行情暂时不可用"，不影响基金数据；
- 分时数据直连东财 `trends2`（约 0.2 秒）：AkShare 的分钟封装会分 17 页拉取，实测 22 秒，
  详情页等不起，见 `app/datasources/eastmoney.py` 的说明；
- 数据源为东方财富公开行情（AkShare + 分时直连），盘中延迟约数秒到十几秒，
  非交易时段返回最近收盘值，用 `trade_date` 标明归属交易日。

### 门户 · 内容（公开）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/portal/articles` | 已发布文章列表，支持 `keyword` / `category`（policy/market/company/other） / 分页 |
| GET | `/portal/articles/{slug}` | 文章详情（浏览数 +1） |

文章响应额外带 `category`、`source`、`source_name`、`source_url`、`origin`。
`origin=sync` 表示外部快讯摘编：只有标题、摘要、来源与原文链接，**没有正文**，
前端会显示来源署名和「查看原文」，并注明不构成投资建议。外部快讯默认进草稿，
需后台审核发布后才出现在门户。

### 后台 · 认证（staff_users 表）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/admin/auth/login` | 公开 | 员工登录（令牌 scope=staff） |
| POST | `/admin/auth/refresh` | 公开 | 刷新令牌 |
| GET | `/admin/auth/me` | 登录 | 当前员工 |
| POST | `/admin/auth/change-password` | 登录 | 修改密码 |

### 后台 · 员工（仅超管，staff_users 表）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/staff` | 员工列表（keyword / is_active） |
| POST | `/admin/staff` | 创建员工账号（可指定超管） |
| GET | `/admin/staff/{id}` | 详情 |
| PATCH | `/admin/staff/{id}` | 更新（含重置密码 / 禁用 / 升降超管） |
| DELETE | `/admin/staff/{id}` | 软删除 |
| POST | `/admin/staff/batch-delete` | 批量软删除，body `{ids:[1..100]}`；操作者本人自动跳过 |

### 后台 · 用户（超管，门户会员 users 表）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 会员列表（keyword / is_active） |
| POST | `/admin/users` | 创建会员 |
| GET | `/admin/users/{id}` | 详情 |
| PATCH | `/admin/users/{id}` | 更新 |
| DELETE | `/admin/users/{id}` | 软删除 |
| POST | `/admin/users/batch-delete` | 批量软删除，body `{ids:[1..100]}` |

### 后台 · 会员支持（仅超管）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/support/feedback` | 反馈工单（status / category / keyword，分页，带会员标识） |
| PATCH | `/admin/support/feedback/{id}` | 更新状态与公开回复 |
| GET | `/admin/support/password-resets?status=pending` | 重置申请（pending=待核实 / issued=已生成链接 / used=已使用） |
| POST | `/admin/support/members/{id}/reset-link` | 生成一次性重置链接，令牌只返回一次 |
| GET | `/admin/support/members/{id}` | 会员支持概览：关注/交易/持仓数、待处理反馈、待核实重置 |
| GET | `/admin/support/members/{id}/portfolio` | 交易明细**只读**排查，每次查看写一条审计（resource=member_portfolio） |

### 后台 · 内容

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/articles` | 文章列表（status / keyword） |
| POST | `/admin/articles` | 创建文章 |
| GET | `/admin/articles/{id}` | 详情 |
| PATCH | `/admin/articles/{id}` | 更新（含发布/撤回） |
| DELETE | `/admin/articles/{id}` | 软删除 |
| POST | `/admin/articles/batch-delete` | 批量软删除 |
| POST | `/admin/articles/batch-status` | 批量发布 / 撤回，body `{ids, status}` |
| GET | `/admin/articles/{id}/versions` | 历史版本列表（每次保存追加一条快照） |
| POST | `/admin/articles/{id}/versions/{version}/restore` | 恢复到该版本并追加新版本，历史不被覆盖 |

批量操作返回 `data.affected`（实际受影响行数，不存在的 ID 被跳过）。

### 后台 · 概览（登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/dashboard` | 运营概览：核心计数、数据覆盖率、类型分布、最近用户与最近操作，一次返回 |
| GET | `/admin/dashboard/engagement` | 运营效果：7/30 日活跃（含今天 N 个自然日，北京时间）、回访、次周留存、关注与记账转化（已排除测试帐号），含近 14 天日活 |
| GET | `/admin/system/info` | 系统信息（**仅超管**）：运行环境、Python 版本、启动时间、各业务表行数 |
| GET | `/admin/system/health` | 运行健康度（**仅超管**）：日志文件、备份状态与恢复演练结果、汇总告警 |

### 后台 · 审计（仅超管）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/audit-logs` | 操作日志查询（username 模糊 / resource / status_code / 时间范围，分页） |

后台所有写操作（`POST/PATCH/PUT/DELETE`，路径前缀 `/admin/**`）由
`AuditMiddleware` 自动落库到 `audit_logs` 表，业务代码零埋点。
记录内容：操作人、动作、资源、状态码、IP、耗时；**不记录请求体**（避免密码/令牌泄漏）。
登录成功后回填操作人，失败尝试仅保留 IP，可用于暴力破解排查。

### 后台 · 基金

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/funds` | 基金数据列表 |
| GET | `/admin/funds/sync-status` | 同步状态（基金总数、净值行数、最新净值日） |
| POST | `/admin/funds/sync` | **立即同步（仅超管）**，body `{mode, limit?, codes?, force?}`；返回 `SyncJobRead`。`mode=news` 为资讯快讯同步 |
| GET | `/admin/funds/sync/jobs?limit=20` | 同步任务历史（倒序） |
| GET | `/admin/funds/sync/jobs/{id}` | 单个任务详情，前端轮询用 |
| POST | `/admin/funds/sync/jobs/{id}/cancel` | 请求取消：放标记文件，脚本在检查点退出；已结束返回 409 |
| POST | `/admin/funds/sync/jobs/{id}/retry` | 用原模式与参数创建新任务，原记录不可变 |
| GET | `/admin/funds/sync/alerts?hours=24` | 失败/超时任务与长时间无进度的告警 |
| GET | `/admin/funds/sync/schedules` | 定时采集配置 |
| POST | `/admin/funds/sync/schedules` | 新增定时（mode/hour/minute/weekdays/enabled） |
| PATCH | `/admin/funds/sync/schedules/{id}` | 调整或启停 |
| DELETE | `/admin/funds/sync/schedules/{id}` | 删除 |

**资讯快讯同步（`mode=news`）**：`SyncJobService.spawn` 会改用 `scripts.sync_news`
子进程，其余（任务表、日志、结果文件、并发 409、审计）完全复用基金同步通道。
采集源为 AkShare 的东财全球快讯 / 财联社电报 / 同花顺快讯 / 东财财经早餐
（实测单次 0.2–0.6 秒），归一化后做指纹去重 + 跨源标题相似度去重 + 相关性过滤，
按关键词分到 policy / market / company。只保存标题、摘要、来源、原文链接，
`status=draft`、`content=NULL`，由编辑在后台审核或批量发布。
合规性：不全文转载、标注来源、注明不构成投资建议、遵守来源站访问频率。

**手动同步执行模型**：接口创建 `sync_jobs` 记录后立即返回，采集脚本以
`asyncio.create_subprocess_exec` 在**独立子进程**运行（不能在 API 进程内直接调
`run()`：脚本会 `dispose_engine()` 并新建事件循环，会破坏 API 连接池）。
脚本通过 `--job-id` 写 `logs/sync_job_{id}.result.json`，API watcher / 查询接口据此
回填状态；即使 API 重启也能从结果文件恢复，不会留下永远 running 的僵尸任务。
同一时间只允许一个任务（重复触发返回 409）。`POST` 由审计中间件自动记录操作人。
前端入口：后台「采集监控 → 立即同步」，运行中每 3 秒轮询任务状态。

**任务中心**：脚本运行期间把阶段与计数写入 `logs/sync_job_{id}.progress.json`
（phase/total/succeeded/failed/skipped/failures），API 轮询时回填到 `sync_jobs` 并更新心跳；
结果文件额外带 `counts`，进程结束后统计不丢。状态机为
`starting → running → success | partial_success | failed | cancelled | timeout`：
`partial_success` 表示主体完成但有失败条目，`timeout` 由 watcher 按 `timeout_seconds`
终止子进程后写入。定时调度由进程内循环每分钟检查 `sync_schedules`（同一天只跑一次，
被运行中任务占用时 6 小时内补跑），多 worker 靠数据库互斥去重，详见 [ADR-0015](adr/0015-in-process-sync-scheduler.md)。

### 后台 · AI

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/ai/status` | 能力状态（是否启用、模型、是否就绪） |
| POST | `/admin/ai/chat` | 内容助手对话（`message` + 可选 `thread_id`） |
| POST | `/admin/ai/review` | 文章质检（规则校验 + 模型建议） |

未配置模型密钥时返回 `503` / `code=50300`，不影响其他接口。

### 公共

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 存活探针 |
| GET | `/health/db` | 数据库连通性 |

## 文档入口

接口文档按消费方拆成两份，各自只展示自己那部分：

| 文档 | 地址 | 范围 |
| --- | --- | --- |
| 门户接口文档 | <http://127.0.0.1:8000/docs/portal> | `/portal/**` |
| 后台接口文档 | <http://127.0.0.1:8000/docs/admin> | `/admin/**` |
| 全量文档 | <http://127.0.0.1:8000/docs> | 全部路径，排查跨端问题时用 |

对应的 schema 分别是 `/openapi/portal.json`、`/openapi/admin.json`、`/openapi.json`。
切分在 `app/core/openapi.py` 里按路径前缀完成，**不拆服务、不复制路由**，新增接口自动归入对应文档。

## 约定细节

- 时间统一为 `YYYY-MM-DDTHH:MM:SS`（本地时区，无时区后缀），前端负责展示格式化。
- 删除为**软删除**（`deleted_at` 置位），列表默认过滤已删除数据。
- 文章 `slug` 唯一，留空时由标题生成；中文标题会退化为 `post-xxxxxxxx`。
- 列表接口的 `keyword` 为模糊匹配，后端做长度保护，避免全表扫描（可按需加索引）。
- 基金价格类字段（收益、净值）带正负号；**幅度类字段**（回撤、波动率）为正值，
  前端展示时不要加 `+`。
- **费率语义**：`fee_rate` = 管理费率、`custody_fee` = 托管费率（均 %/年，来自雪球费用明细）。
  采集不到时为 `null`，前端显示 `—`，**绝不写 0 兜底**——排行接口的"手续费"是申购费
  （C 类为 0），与管理费是两回事，不能混用。
- 重仓股 `rank` 不信任数据源的"序号"（有时是季度内排名、有时是全年累计），
  采集时按季度分组、占净值比例降序重排。
- **风险等级与主题板块都是"规则推导"，不是官方定级/分类**（无公开数据源）：
  - `risk_level` 按基金类型推导（`sync_funds.py --mode risk-level`）：货币→低、债券→中低、
    FOF→中、混合/指数→中高、股票/QDII→高，只填 NULL。口径同支付宝 R1–R5 适当性分类。
  - `sector` 按基金简称/全称/跟踪指数关键词推导（`--mode sector`，规则集中在
    `app/fund_sectors.py`），特异度高的主题优先（半导体 > 科技、新能源 > 制造）。
    无主题词则保持 NULL（前端显示"综合"）；`--force` 可按最新规则全量重算。
    识别前必须剥离"证券投资基金"等通用后缀，否则"证券"会把全库误判为金融板块。

简化录入补充：`transactions/timing` / `applications` 支持 `pricing_rule=auto`，响应返回实际采用的 cn_open/platform。特殊品种和日历未知范围保留 expected_nav_on=null；auto 不吞掉非法时区、未来申请时间或早于成立日等输入错误。applications 的 platform 可省略/为 null，保存为空字符串表示未知，补充回执时允许填写真实平台；已知平台仍不允许悄悄变更。


### 自动查询记账

`POST /portal/me/auto-transactions` 接收与 ApplicationInput 相同的 code/kind/submitted_at/amount或shares/request_key，platform可选。自动查同日净值与公开费率，返回 `{status: recorded|pending, transaction?, application?, message}`。价格或费率未知不生成虚假零费用；齐全时 record_source=estimated 入账，calculation_basis 保存公开费率来源、查询时间、档位、批次持有期与费用。用户回执仍为 receipt。

待处理记录增加 automatic_processing / processing_message，只有明确由自动入口创建的申请才会自动补齐。`GET /portal/me/applications` 会尝试补齐最多5笔自动记录；已有 quick/navs/all 同步后可补齐待处理，不引入额外调度。组合与基金明细增加 estimated_count；calculated_count 只指旧折算。


### 统一交易记录与清理

`GET /portal/me/records` 以数据库UNION汇总交易与申请，返回 `PageResult[TradeHistoryItem]`：
`page`从1开始，`page_size`为1–100；`keyword`按基金名称或代码包含匹配（转义%/_）；`kind=buy|sell`；`status=pending|confirmed|cancelled|voided`；`start/end`是北京时间下单日期范围，包含两端，起止倒置返回422。
每项增加 `record_type=transaction|application`、`can_cancel/can_void/can_delete`、requires_review；未成交的nav/fee/cash_amount为null，不填0。基金成交后关联申请不重复显示。

`DELETE /portal/me/transactions/{id}` 仅删除已作废记录，`DELETE /portal/me/applications/{id}` 仅删除已撤销记录；操作按当前用户隔离，越权404，有效/待入账记录409。删除使用墓碑保持请求幂等，旧确认或自动记账重试不能复活已删除记录。

自动计算新增公开买入/卖出T+N确认周期，净值日按已核对交易日历推进；确认期前保持pending。无公开确认规则时继续等待，不假定当晚入账。本站取消记录不调用外部平台撤单接口。

旧 `GET /portal/me/transactions` 保留成交流水结构与原分页参数；门户统一记录使用新增 `/records`，不改变旧调用方对已成交流水的读取。
