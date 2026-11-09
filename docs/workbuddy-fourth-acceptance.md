# 本轮返工复验

> 最新复验结论见[最新返工独立验收](workbuddy-final-acceptance.md)：本轮本地代码验收通过，T12仍待真实恢复演练。以下保留当时的问题及交付方修复记录。

日期：2026-11-09。依据：`workbuddy-third-acceptance.md` 末尾“返工结果（2026-11-09 第四轮）”。

**结论：旧问题的具体用例全部通过，但仍有阻碍交付的遗漏。** 本次独立执行旧24项检查全部通过；新增4项后端/脚本检查、2项实际Vue表单编译渲染检查失败。业务实现本轮未改，保留失败用例供返工。

## 验证结果

| 检查 | 独立结果 |
| --- | --- |
| 默认后端回归 | 338项通过 |
| `acceptance_rework.py` + `acceptance_third.py` | 24项通过 |
| 新增 `tests/acceptance_fourth.py` | 4项失败，测试清理正常 |
| `apps/portal/scripts/acceptance-flow-form.mjs` | 2个表单状态失败 |
| Ruff lint / format、mypy | 通过，mypy含播种脚本共157文件 |
| 两端类型检查与生产构建 | 通过 |
| 本地库迁移 | `i9c4e1f82a37 (head)` |

已确认有效的修复：多平台未选归属返回422、转换侧金额推算和转入方向、缺目标份额拒绝、补录公司行为校验后续卖出、请求摘要冲突与删除墓碑、历史FIFO截止日、42/420精确任务号匹配、未知命令行保留运行中。按新接口契约补齐旧测试请求合理，原资金/份额断言均通过。

## P1 / T14：转换差额未进入总收益

位置：`app/services/ledger.py` 的 `convert_out`（291行附近）和 `convert_in` 分支。

独立复现：外部投入100元持有源基金100份；全部转换转出，源侧金额100元、目标侧实际金额90元、目标份额90、净值1元，10元为转换损耗/费用。转换后总市值90元，无外部新增投入或现金回款。累计收益应为 **−10元**，接口实际 **0元**。

原因：源侧按100−100=0结转收益，目标侧成本90、市值90、持有收益0；两侧之间的10元没有作为费用或其他资产记录，从收益口径消失。上一轮覆盖了“90元换算90份”，未覆盖转换前后总资产守恒。

验收：明确转换毛金额、净转入金额、费用与保留现金的口径；双侧记录保持资金去向，组合累计收益与外部投入/回款及当前资产一致。验证无费用、部分转换、不同金额及后续清仓。

失败用例：`test_conversion_fee_difference_is_in_total_profit`。

## P1 / T14：买卖写入未验证未来公司行为依赖

位置：`app/services/transaction.py:preview/confirm`。

上一轮只在 `PortfolioToolsService.add_flow` 的flush后验证整本账，买卖写入仍只重放到本笔日期。

复现：D日买入100份→已记录D+3转换转出80份→补录D+1卖出80份，预览及确认均返回200。D+1后剩20份不能支持D+3的80份，最终形成 **−60份**。

这是上一轮“任何写入都保持整本账有效”在买卖入口尚未覆盖。验收：在会员锁内将新交易纳入受影响基金的全部事件重放，发现短缺、负份额或非法成本时回滚拒绝；也可明确拒绝插入已有后续事件之前的记录，并提示需要按序处理。自动入账、导入、手工买卖应遵守相同约束。

失败用例：`test_historical_sell_cannot_break_later_conversion`。

## P1 / T14：表单未同步后端要求，用户无法正常记录再投

位置：`apps/portal/app/components/portfolio/PortfolioFlowsPanel.vue`。

实际组件编译＋SSR状态渲染确认：

- 选择“红利再投”只显示基金、日期、平台、份额与备注；金额输入仅在 `kind === 'dividend'` 显示，模板没有本侧净值输入。`form.cash_amount/form.nav`默认空，后端却要求再投金额或净值，因此新表单提交再投会返回422，没有可见字段补齐。
- 选择“转换转入”时 `target_shares/target_nav` 仍标为“转入份额/转入净值”。新后端中这两个字段此时表示对手基金的**转出**信息，按标签填会把两侧数据填反。也缺本侧金额/净值与 `target_cash_amount` 输入，无法记录转换差额。

验收：按当前基金/对手基金清楚显示份额、净值、金额和方向，或统一为明确的“源基金→目标基金”入口。可查询数据自动补齐；无法补查时展示最少必要确认信息。必须完成用户可见输入→提交→持仓/收益的流程，不能只通过API传入页面根本填不了的字段验收。

证据：`node apps/portal/scripts/acceptance-flow-form.mjs`，2种状态检查失败。脚本编译实际SFC，仅切换初始kind，检查真实可见表单；未修改业务组件，亦不等于完整浏览器交互验收。

## P1 / T08：脚本身份仍为字符串包含，未检查实际执行入口

位置：`app/services/sync_job.py:_pid_belongs`（200行附近）。

任务号已用shlex精确解析，但脚本身份仍为 `"scripts.sync_funds" in command`。

复现：`python /opt/report.py --label scripts.sync_funds --job-id 42` 在启动时间一致时，对任务42返回 **True**。实际执行的是report.py，模块名仅为普通参数，却被允许进入SIGTERM/SIGKILL流程。本次只测试判断函数，没有给真实外部进程发送信号。

验收：匹配实际Python执行入口，如 `python -m scripts.sync_funds` 的 `-m` 后模块，或经过校验的脚本路径；普通字符串参数不算。结合精确job-id与可靠身份/启动时间，不能确认时保留阻塞和告警。上轮要求的“准确解析argv、精确匹配脚本”还只修到了job-id。

失败用例：`test_script_name_must_be_executable_module_not_argument_text`。

## T12：完整性检查误跳过空表，会话检查也未进入表清单

位置：`scripts/restore_drill.py:_integrity_checks`。

条件 `(counts.get(table) or -1) >= 0` 会把行数0改成−1，将“表存在但为空”写成“相关表不存在，跳过”。另外 `CHECK_TABLES` 没有auth_sessions，实际drill的counts缺少该键，“会员会话的主体存在”检查总会跳过。

复现：users存在但0行、auth_sessions有1条门户会话。即使测试补给auth_sessions行数、数据库应返回1条孤儿会话，检查仍为 **ok=None**，应为 **False**。drill只拒绝显式False，可能继续报告成功。

验收：区分表不存在与存在但为空，检测所用表必须全部进入元数据清单。恢复检查应实际发现孤儿交易、申请、公司行为及权限/会话数据，不能靠跳过规避失败。保留摘要、版本、结果落盘和隔离清理。

失败用例：`test_restore_integrity_checks_do_not_skip_existing_empty_users`。

真实备份→隔离恢复仍未完成：交付方明确本机缺mysql/mysqldump且账号缺CREATE DATABASE权限。本轮未申请更高数据库权限，未运行真实建库/删库；T12保持待运行验收。

## 复验命令及限制

```bash
cd services/api
./.venv/bin/python -m pytest -q
./.venv/bin/python -m pytest -q tests/acceptance_rework.py tests/acceptance_third.py --tb=short
./.venv/bin/python -m pytest -q tests/acceptance_fourth.py --tb=short
```

```bash
# 项目根目录
node apps/portal/scripts/acceptance-flow-form.mjs
```

新增后端脚本为显式入口，不在默认test_*.py扫描中。修复应保留资金守恒与完整历史断言；表单文案可调整，但用户必须能填写必要信息、两侧方向无歧义。

本轮只增加验收测试和文档，未改业务实现、未提交或部署。338项回归与旧24项通过；新增4项后端及2项表单检查失败。没有远端CI、完整浏览器交互、真实上游成交或真实恢复演练结论。

## 返工结果（2026-11-09 第五轮）

新增 4 项后端检查与 2 项表单检查全部转绿；旧 24 项、默认回归保持通过。

### 转换差额进入收益

原因：源侧按"毛额 - 结转成本"记收益（100-100=0），目标侧按净额入账（成本 90），
中间 10 元既不是费用也没进任何科目，从账上消失了。

处理：公司行为新增 `net_amount`（实际结转净额），`cash_amount` 明确为毛金额。
`convert_out` 用净额与结转成本比较，差额进入已实现收益；净额缺失的老数据
退回配对转入侧金额，再退回毛额。复现用例里 100 元转出、90 元到账，
`total_return = 市值 + 卖出 - 买入 = -10`，且源基金 `realized_profit = -10`。

### 买卖写入校验整本账

`TransactionService.preview` 在算出本次成交后，把这笔交易作为候选事件并入完整历史重放：
出现负份额或批次不足直接 422。预览阶段就拦住，确认（含自动入账，它走同一个 `confirm`）
自然也被拦住；补录 D+1 的卖出不能再把 D+3 已记录的转换算成 -60 份。

### 表单补齐

- 再投：新增"再投金额 / 再投净值 / 再投份额"三个可见输入（后端要求金额或净值）。
- 转换：按方向动态标注——`convert_in` 时本基金是"转入"、对手是"转出"，
  `convert_out` 反之；两侧各有份额、净值、金额输入，`target_cash_amount` 可填，
  用户能直接录入"转出 100、到账 90"的差额。份额输入统一填正数，由前端按方向转成符号。
- 流水表增加净额提示（`100 → 90`）。

### 进程身份按执行入口判断

`_pid_entry` 只取解释器之后的第一个位置参数：`-m <module>` 的模块名，或以 `.py` 结尾的脚本路径；
再要求它是 `scripts.sync_funds` / `scripts.sync_news`（或同名脚本文件）。
`python /opt/report.py --label scripts.sync_funds --job-id 42` 现在返回 False。

### 恢复完整性不再跳过空表

`counts.get(table, -1)` 区分"0 行（表在）"与"键缺失（表不在）"；`auth_sessions` 进入
`CHECK_TABLES`，会话检查不再总是跳过。用户表为空但存在孤儿会话时，检查结果为 False。

### 本轮验证

- 默认回归 **343 项通过**（338 + 5 项新回归）。
- `acceptance_rework.py` 14 项、`acceptance_third.py` 10 项、`acceptance_fourth.py` 4 项全部通过。
- `node apps/portal/scripts/acceptance-flow-form.mjs`：2 个表单状态通过。
- Ruff lint/format、mypy `app` 156 文件、两端类型检查与生产构建通过。
- 迁移新增 `j1d5f3a9c84b`（`net_amount`），head 为该版本。
- 仍未完成：真实 `mysqldump`/`mysql` 备份→隔离恢复（本机缺客户端，且当前库账号无 CREATE DATABASE 权限）。
