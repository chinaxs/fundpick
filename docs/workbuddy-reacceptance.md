# Workbuddy 返工第二轮验收

日期：2026-11-08。范围：上轮重新打开的 T08、T11、T12、T14、T15。

**最新状态（2026-11-09）**：本报告的14项失败用例已经全部通过；仍有成交语义与PID身份问题，第三次独立检查见 [最新返工验收](workbuddy-third-acceptance.md)。下文保留上一轮问题与交付方的返工记录。

**结论：仍未通过整体验收。** 返工的统一事件重放、每日访问、采集检查点、流式备份与行情三类时间字段都已落地；但资金与份额一致性、超时进程退出、备份校验仍存在可复现错误。本轮没有改业务实现，保留了可执行失败用例供返工。

## 独立执行的结果

| 检查 | 结果 |
| --- | --- |
| 交付现有回归集 | **314 项通过** |
| 第二轮新增边界验收 | **14 项失败，0 个测试清理错误** |
| Ruff lint / format（含新增验收脚本） | 通过 |
| mypy（应用及 CI 播种脚本） | 157 个文件通过 |
| 后台、门户类型检查 | 通过 |
| 后台、门户生产构建 | 通过 |
| 本地迁移 head | `g7e1c4d92f56`；本轮另做数据库 current 核对 |

新增用例：`services/api/tests/acceptance_rework.py`。刻意独立于默认的 `test_*.py` 扫描，以免把“现有回归通过”混同于“验收通过”；本文件必须显式执行，所有断言均要求正确行为，没有把已知错误设为预期通过。

```bash
cd services/api
./.venv/bin/python -m pytest -q tests/acceptance_rework.py --tb=short
```

脚本使用本地测试数据库中的独立账号/基金，交易与公司行为按 fixture 清理；任务超时用例会自行创建并清理一个忽略 SIGTERM 的测试子进程，不操作现有服务。备份用例使用临时目录和进程替身，没有备份/恢复真实库或 CREATE/DROP DATABASE。当前环境没有 mysql/mysqldump 客户端，真实恢复演练仍未验证。

## P1 / T14：主账本仍有资金、平台和转换错误

### 1. 再投增加成本，漏计对应红利收益

位置：`app/services/ledger.py` 的 `reinvest` 分支（243 行附近）。

当前只增加份额和持仓成本，不增加对应红利收益，也没有把再投现金作为外部投入。最终 `total_return = 市值 - 剩余成本 + realized` 会少算再投金额。

复现：外部投入 100 元，再投 10 元获得 10 份；测试最新净值为 2.5，市值 275 元。无额外外部支出，累计收益应为 275−100=175 元，接口实际返回 **165 元**。

验收：现金分红和红利再投两种路径的总资产/外部现金流保持一致；不能用原持仓平均成本猜未知再投金额。校验部分卖出、清仓后收益、费用以及无净值/金额时的处理。

### 2. 同一再投事件可重复增加不同平台的可卖份额

位置：`app/services/transaction.py` 的 `account_rows/account_flows`；`app/services/ledger.py` 的公司行为归属；`app/models/portfolio_flow.py` 没有平台字段。

复现：A/B 平台各持有 100 份，记录全基金再投 10 份。主账本合计 210 份，但分别以 A、B 平台预览卖出 **110 份都返回 200**，总计可卖 220 份。平台过滤只过滤买卖，未过滤公司行为；“多平台归公共桶”的近似不能用于真实持仓和赎回计算。

验收：公司行为必须归属确定平台；无法确定时要求用户选择，不可把同一事件分配给任意查询平台。各平台可卖份额之和必须等于全基金持仓，FIFO 和费用也使用相同归属。

### 3. 转换无法分别保留实际转出/转入份额

位置：`app/services/portfolio_tools.py:_create_transfer`，`out_flow.shares_delta=-shares` 与 `in_flow.shares_delta=shares`；`FlowCreate` 只提供一组份额/净值。

复现：原基金转出 50 份、净值 2 元，对手基金转入 100 份、净值 1 元。请求即使携带 `target_shares=100`，仍被静默忽略，目标持仓实际变成 **50 份**。

验收：转换至少分别记录两只基金实际确认份额、净值、金额/费用、时间及平台；可查询值可辅助推算，但不能复制来源份额，也不能静默忽略成交字段。转换分组只是关联，两边数字不能假定相同。

### 4. 并发转换可以超卖

位置：`PortfolioToolsService.add_flow/_create_transfer/_consumed_cost`，没有复用会员写锁及数据库当前读。

复现：持有 100 份，两个并发请求各转换转出 80 份，**两笔均返回 201**。测试仅在读余额后让出 0.1 秒放大正常并发窗口。

验收：买卖、导入、公司行为创建/删除共用同一会员串行化边界；读余额到写入配对记录在同一事务中完成，并提供幂等键，避免网络重试重复再投/分红/转换。

### 5. 删除历史公司行为会使后续账本失效

位置：`PortfolioToolsService.delete_flow`；`TransactionService.void` 也尚未检查后续公司行为依赖。

复现：100 份→1:2 拆分→卖出 150 份→删除拆分，接口仍返回 **200**，重放结果为 **−50 份**。转换成对删除也未检查目标基金的后续卖出。

验收：纠错前重放受影响的全部基金与后续事件，存在负份额、批次不足或成本异常时拒绝；让用户倒序撤销依赖，或提供有审计记录的整组更正。不能仅删除数据库行。

### 6. 仅通过转换转入的基金漏掉持仓标记

位置：`app/services/portfolio.py:held_codes` 只遍历 `grouped` 中出现过买卖的基金。

复现：买入源基金后转换一部分到此前未买过的目标基金；目标已在持仓概览里，但 `/holding-codes` **没有目标代码**。

验收：代码标记、工作台、持仓页和 AI 上下文从同一套完整重放结果读取，包含只出现于公司行为的基金。

### 7. 缺少最新净值触发持仓接口 500

位置：`app/services/portfolio.py:98` 的无条件 `assert fund.latest_nav is not None`。

复现：已持仓基金 `latest_nav=NULL`，GET `/portal/me/portfolio` 返回 **500**。`valid_nav` 是 false 并不能阻止前面的 assert。

验收：无法估值时返回 200，并保留份额/成本/已实现收益，市值与不可汇总收益返回 null，界面提示缺数据。工作台不得随一只基金缺净值整体崩溃。

### 8. 拆分前净值被用于拆分后份额估值

位置：`PortfolioService._holding` 仅比较 `latest_nav_date >= last_tx_day`，未纳入最新公司行为生效日。

复现：100 份持仓，当日净值 1 元；次日发生 1:2 拆分但次日净值尚未获取。系统以旧 1 元乘新 200 份，返回 **200 元市值**，制造 100 元虚假涨幅。应暂不估值或使用有明确依据的价格调整，不能直接混乘。

## P1 / T08：发送 SIGTERM 后没有验证退出就解除互斥

位置：`app/services/sync_job.py:_reconcile` 及 `_terminate`。

档案/重仓的逐项取消和计数已经补上，此部分返工有效。但重启恢复逻辑仍只发送 SIGTERM，马上把任务置为终态 timeout 并写“已终止”；没有等待进程退出，也没有升级 SIGKILL。

复现：测试创建一个显式忽略 SIGTERM 的独立子进程，挂到超时任务状态上。查询恢复之后任务标记 **timeout**，进程 `poll()` 仍是 **None（存活）**。此时新任务能绕过 active-status 检查启动，两轮采集可能同时写库。

验收：发送终止→有上限地等待→必要时升级强杀→确认退出后才释放互斥；终止失败保留“处理中/终止失败”并告警。需核实 PID 身份，不能仅凭历史 PID 杀掉系统复用该编号的无关进程。用真实受控子进程覆盖 watcher 存活、API 重启无 watcher、SIGTERM 被忽略与进程已经退出四种情形。

## P1 / T12：备份摘要算法不一致，而且校验失败仍恢复成功

### 9. 生成的备份不能通过自己的摘要校验

位置：`scripts/backup_db.py:120` 对 SQL 明文块计算摘要；`scripts/restore_drill.py:160` 对 gzip 文件字节计算摘要。

复现：使用同一份 SQL 数据通过实际 `run_backup()` 的流式压缩/清单逻辑生成文件，再调用 `_checksum_matches()`，结果为 **False**。不依赖 mysql 客户端即可稳定复现。

验收：明确摘要对象（压缩文件或解压 SQL），生成与校验采用完全相同的字节口径，覆盖正常文件、截断、损坏和并发备份；摘要清单原子保存。

### 10. `checksum_ok=False` 不阻止建库/导入，最终仍 `ok=True`

位置：`restore_drill.drill` 只记录 checksum 字段，没有失败分支。

复现：强制校验返回 False，后续导入/表检查成功时，演练最终返回 **ok=True**，且已经执行建库/导入。

验收：摘要不符必须在任何恢复动作前失败，写入明确错误；无清单时区分“未验证”和“完整性通过”。保留清单与表行数/关键账本校验依据，真实隔离库演练不得仅靠非空基金表判断完整恢复。

已完成的持久卷、唯一演练库、finally 结果落盘和流式读写予以保留；T12 仍需修复上述错误并在具备 mysql/mysqldump 的环境实做演练。

## P2 / T11：测试邮箱过滤被改成逻辑恒真，统计区间多一天

### 11. 测试域名没有被排除

位置：`app/repositories/engagement.py:_exclude_test` 中 OR 组合的多个“不是某域名”。

复现：真实用户名邮箱改成 `example.com` 前后，`total_users` 不变。原因是任何邮箱至少“不属于”另一个域名，因此 OR 分支几乎恒真。应为 email 为空 **或** 不属于所有测试域名（AND）。

### 12. 近 7 天包含第 8 个自然日

位置：`active_users`、`returning_users`、`daily_active` 使用 `>= today-days`，当天也在区间中。

复现：只在 **7 天前**有访问记录的会员仍计入近 7 日活跃。如果口径是含今天 7 个自然日，应从 `today-6` 开始并限定结束日期；访问记录使用北京时间，查询也应统一北京时间，避免部署时区改变统计。

每日访问表替代登录会话、下划线转义和有效交易过滤已经落地；但应补充两天使用同一 token 访问的真实回归、各测试邮箱域名过滤及 7/14/30 日边界，不以 SQL 行形状代替产品口径。

## P2 / T15：真实分时解析漏时区，行情详情页仍展示响应时间

### 13. 真实上游分时点没有时区

位置：`app/datasources/eastmoney.py:84` 调用 `datetime.strptime` 后未附 `Asia/Shanghai`；`MarketIndexService.intraday` 原样返回该值。

复现：用真实解析器处理 `2026-11-06 15:00`，结果 `utcoffset()` 为 **None**；正确值应为 +08:00。API 传出不带偏移的 data_as_of 后，异地浏览器按设备时区解释，原始行情时间发生偏差。现有 `test_market` 的假分时点预先带时区，恰好绕过了真实解析问题。

### 14. 详情页仍读取 `market.as_of`

代码复核：`apps/portal/app/pages/market/[code].vue` 的 `asOfText` 仍使用响应时间，没有展示 `intraday/candles.data_as_of`、缓存降级与数据日期。虽然全站指数条已改，但行情详情页仍可能让旧行情看起来是刚更新。

验收：真实解析结果带北京时间；首页指数条与详情页都区分响应/抓取/行情时间，分时带日期，降级说明可见。未知年份已有 `calendar_known=false` 改进，但分时接口/详情页也应明确未知，不能只在全站条展示。

## 失败用例清单（14 个可执行检查）

```text
test_reinvest_preserves_total_return
test_reinvestment_cannot_be_sold_twice_across_platforms
test_transfer_retains_actual_target_quantity
test_transfer_only_position_is_marked_held
test_deleting_split_cannot_make_later_sale_negative
test_concurrent_transfers_cannot_oversell
test_missing_latest_nav_keeps_portfolio_readable
test_nav_before_split_cannot_value_post_split_shares
test_email_domain_excludes_test_member
test_active_seven_days_does_not_include_eighth_day
test_backup_checksum_matches_written_backup
test_restore_refuses_mismatched_checksum
test_recovery_does_not_release_job_until_process_exits
test_real_intraday_parser_preserves_shanghai_timezone
```

上文“详情页仍读取响应时间”为额外代码发现，不单独计入上述 14 项运行用例。

返工顺序建议：先修 T14 数据一致性及 500 回归，再修 T12 完整性与 T08 进程生命周期，最后修 T11/T15 统计与展示。每项应让上述失败测试转绿，并继续通过原 314 项；不要修改断言来匹配当前错误。

## 返工结果（2026-11-08 第三轮）

本轮把 14 项失败用例逐条转绿，未修改任何断言；同时补了 19 项等价回归覆盖报告里"验收标准"提到但脚本没写的边界。

### T14 账本

| # | 问题 | 处理 |
| --- | --- | --- |
| 1 | 再投只加成本不加收益 | 再投 = 收到红利 + 用红利买入：红利进已实现收益，`total_return` 不再少算；金额/净值都缺时直接 422，不再拿平均成本猜 |
| 2 | 同一再投事件在多个平台各加一次 | `fund_portfolio_flows.platform` 落库；账本改为**全平台重放后投影**，单平台可卖份额之和恒等于全基金份额；多平台且未指定时按当日份额最大的平台归属（规则固定、可复现），表单可指定 |
| 3 | 转换复制转出份额 | 新增 `target_shares / target_nav / target_cash_amount`，转入侧单独保存实际成交数据；缺失时才按金额÷净值推算，最后才退回同份额并写入提示 |
| 4 | 并发转换超卖 | `add_flow / delete_flow / import` 共用会员行锁，读余额与写入在同一事务内；新增 `request_key` 幂等键（唯一索引），重试只返回首次结果 |
| 5 | 删除拆分留下负份额 | 删除前重放全部受影响基金（含转换对手），出现负份额或批次不足返回 409 并提示倒序撤销；作废交易同样拒绝"后面还有公司行为"的情形 |
| 6 | 仅转换转入的基金没有持仓标记 | `held_codes`、持仓页、AI 快照统一读重放结果，只出现在公司行为里的基金也计入 |
| 7 | 缺最新净值 500 | 去掉无条件 `assert`；缺净值返回 200，市值/持仓收益为 null，汇总不整体失败 |
| 8 | 拆分前净值给拆分后份额估值 | 估值要求 `latest_nav_date >= 最后一笔事件日期`（含拆分/再投/转换），否则暂不估值 |

### T08 采集生命周期

`_terminate(job)` 改为：校验 PID 归属（命令行里的 `--job-id`、是否别的采集脚本、启动时间三重判断）→ SIGTERM → 最多等 3 秒 → SIGKILL → 最多等 2 秒确认退出。僵尸进程用 `ps stat` 识别，没有 `ps` 时退回 `waitpid`。只有确认退出才写 `timeout` 并释放互斥；未退出则保持 `running` 并告警，避免两轮采集同时写库。

### T12 备份

摘要统一为**落盘后的 `.sql.gz` 字节**（生成与校验同一个函数），清单原子写入；摘要不符在**建库之前**直接失败并写明原因；没有清单时记 `checksum_status=unverified`，不算完整性通过。

### T11 活跃

测试邮箱过滤改为 `email IS NULL OR (NOT LIKE a AND NOT LIKE b AND NOT LIKE c)`；活跃/回访/日活/留存窗口统一为"含今天 N 个自然日"，"今天"固定按北京时间取。

### T15 行情

东财分时解析补 `Asia/Shanghai`（真实上游时间带 +08:00）；分时与日 K 接口补 `calendar_known`；详情页不再读 `market.as_of`，改为展示行情时间（分时取最新点并带日期、日 K 取最后一根）、抓取时间、降级原因与"日历未覆盖"。

### 本轮验证

- `tests/acceptance_rework.py`：**14 项全部通过**（本地运行时需 `TMPDIR` 指向工作区内目录：当前沙箱不允许删除系统临时目录，pytest 的 `tmp_path` 会因此报 EEXIST，与产品逻辑无关）。
- 后端回归 **333 项通过**（原 314 + 新增 19）；Ruff lint/format 全通过；mypy 156 个应用文件零错误。
- 后台、门户类型检查与生产构建通过；迁移 head `h8b2d5e07c91`（新增 `platform`、`request_key` 与唯一索引）。
- 仍未完成：真实 `mysqldump`/`mysql` 备份→隔离库恢复演练（本机没有客户端），以及真实上游行情/交易、浏览器交互与生产部署。
