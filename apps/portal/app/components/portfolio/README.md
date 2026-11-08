# 外部平台交易记录界面

展示外部平台申请、待确认、回执入账、持仓和流水的闭环。

- `TradeForm.vue` / `TradePreview.vue`：录入与服务端预览；确认后通知页面刷新。
- `Metrics.vue` / `Holdings.vue`：组合统计与按基金合并的持仓。
- `History.vue`：分页流水与作废入口。
- `Legacy.vue`：旧持仓逐笔核对入口。

组件只收 props 和发出事件，交易请求走 `usePortfolio.ts`，录入状态走 `useTradeForm.ts`；计算与权限由服务端处理。弹窗使用已安装的 Element Plus，样式限定于 `portfolio.css` 的 `.trading` / `.trade-flow`。

业务口径见 [交易流程](../../../../../docs/trading-flow.md)。

`TradeHost.vue` 为全站唯一交易弹窗宿主，放在默认布局；基金页和持仓页统一通过 `useTradeDialog` 打开。
页面不再各建一个弹窗，确认后统一刷新持仓代码、组合、工作台与已挂载的流水缓存。

`Applications.vue` 显示未计入持仓的待确认记录，`ReceiptFields.vue` 录入平台实际回执。新流程分开申请时间、净值所属日与平台确认日；旧折算记录显示待核对来源。

默认录入已简化为金额/份额和下单时间，一次保存为待补充记录；不要求用户先选择状态或净值规则。已确认信息从“补充结果”展开，净值日与同日净值可自动带出；确认日可以留空，真实份额与费用仍按平台填写。

自动入口只需金额/份额与时间，由服务查询同日净值和申购/赎回费率；结果标 estimated 并可查看计算依据。交易弹窗已使用 Element Plus 的表单、输入框、折叠、自动补全、中文日期选择与按钮，样式限定为 `.trade-dialog`/`.trade-entry`。`EntryExtras.vue` 管理选填项，`CalculationBasis.vue` 展示查询来源和批次费率。

`HistoryFilters.vue` / `HistoryRow.vue` 分别负责记录筛选与状态操作；`History.vue` 使用Element分页。`Applications.vue` 对正常等待记录只给撤销，对异常显示人工处理。`usePositionBook.ts` 管理筛选、分页、操作后刷新与待入账轮询。

更多持仓操作放在`/portfolio/tools`，由持仓页的次要链接进入，不再占会员主导航。首页只提供买卖入口和三种按需操作：添加已有持仓、分红、转换；收益明细、拆分与导出收在“其他操作”，核对数据仅在打开时请求。

`PortfolioImportPanel.vue`默认提供Element单笔表单（基金、持仓日期、份额、成本），一次保存；CSV批量导入折叠保留。`PortfolioFlowsPanel.vue`按入口展示分红、转换或拆分，分红可切换现金/再投，转换统一以“转出→转入”录入，保留双侧实际份额/金额，金额差计入费用。平台与备注选填、补充记录折叠展示；不改变后台对历史有效性、幂等、费用和多平台归属的校验。
