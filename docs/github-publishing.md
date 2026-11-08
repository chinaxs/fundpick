# GitHub发布资料

## 仓库名称

建议：`fundpick`。名称短且与产品一致；基金与模拟交易关键词放在About、Topics和README中。

## About描述

```text
拾贝 FundPick：开源基金模拟交易、基金持仓管理与投资记账工具，支持净值查询、收益分析、基金筛选和对比。Self-hosted fund paper trading & portfolio tracker built with Nuxt, Vue and FastAPI.
```

## Topics

GitHub Topics使用英文小写与连字符。建议设置：

```text
fund mutual-funds china-funds paper-trading simulated-trading fund-tracker portfolio-tracker portfolio-management investment-tracker personal-finance self-hosted nuxt vue fastapi python typescript akshare
```

README的中文标题、功能段落和英文摘要已包含“基金、基金模拟交易、模拟买卖、持仓管理、投资记账、基金筛选”等关键词。Topics需要在GitHub仓库设置中实际添加，文件内容不会自动成为仓库Topics。

## 首版说明

标题：`v0.1.0 — 基金模拟交易与持仓管理`

正文可使用[CHANGELOG.md](../CHANGELOG.md)的0.1.0段落；同步列出早期版本限制、数据源条件和未完成的生产恢复演练。不要宣传自动执行交易或保证与所有外部平台完全一致。

## 发布顺序

1. 使用最终提交从干净目录验证依赖、迁移、初始化、构建和测试。
2. 执行`python3 scripts/check-secrets.py --history`，确认`.env`、备份、会话与真实会员数据不在提交中。
3. 创建目标GitHub仓库，推送完整提交；仓库地址和账号必须由维护者提供。
4. 填写上述About与Topics；启用Private vulnerability reporting和依赖更新/漏洞提醒。
5. 等待实际GitHub Actions通过，再发布`v0.1.0`标签及Release。Actions尚未运行时不要添加“CI通过”的表述。

本地仓库没有remote或环境没有GitHub登录时，仍可完成全部代码与文档准备，但不能据此声称已经创建或公开GitHub仓库。不要把GitHub Token写入README、remote URL或公开Issue。
