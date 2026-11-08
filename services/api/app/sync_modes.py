"""同步模式白名单：`scripts/sync_funds.py` 的 --mode choices 与后台触发接口共用。"""

SYNC_MODES: tuple[str, ...] = (
    "quick",
    "snapshot",
    "risk",
    "risk-level",
    "sector",
    "pinyin",
    "scale",
    "detail",
    "navs",
    "holdings",
    "news",
    "all",
)

SYNC_MODE_LABELS: dict[str, str] = {
    "quick": "基础数据 / 最新净值",
    "snapshot": "指定基金净值与区间收益",
    "risk": "风险指标（回撤·夏普·波动）",
    "risk-level": "风险等级推导",
    "sector": "主题板块推导",
    "pinyin": "搜索拼音索引",
    "scale": "基金规模",
    "detail": "基金档案与费率",
    "navs": "历史净值序列",
    "holdings": "季度重仓股",
    "news": "资讯快讯（政策 / 市场，进草稿待审核）",
    "all": "全量（耗时很长）",
}
