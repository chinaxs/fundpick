"""基金主题板块识别规则。

公募基金没有统一的"板块"字段，销售平台（支付宝/天天基金）的主题分类
本质上也是按基金名称与跟踪指数归类。这里做**规则推导**：

- 输入：基金简称 + 基金全称 + 跟踪标的指数；
- 输出：单个主板块（特异度最高的规则优先命中），无匹配返回 None；
- 数据来源与口径全部写在本文件，脚本与接口共用，避免前后端各写一套。

注意：名称里不含主题词的主动权益基金、债券/货币基金不会被强行归类，
保持 NULL（前端显示"综合"），不猜测、不造假。
"""

from __future__ import annotations

# 顺序即优先级：越具体的主题排越前，宽泛的"科技/制造/宽基"放最后。
# 例："中证半导体产业指数" → 半导体（不会被 科技TMT/宽基 抢走）
#     "新能源车 ETF"      → 新能源（不会被 高端制造 抢走）
SECTOR_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("ai", "人工智能", ("人工智能", "大模型", "算力", "AI智能", "智能汽车")),
    ("semiconductor", "半导体", ("半导体", "芯片", "集成电路", "存储芯片")),
    (
        "new_energy",
        "新能源",
        ("新能源", "光伏", "锂电", "电池", "储能", "风电", "绿色电力", "清洁能源"),
    ),
    ("military", "军工", ("军工", "国防", "航天", "航空", "兵器", "军民融合")),
    (
        "medicine",
        "医药生物",
        ("医药", "医疗", "创新药", "疫苗", "中药", "生物科技", "生物医药", "CXO", "健康产业"),
    ),
    ("consumer", "消费", ("消费", "白酒", "食品饮料", "食品", "家电", "零售", "酒类", "免税")),
    ("agriculture", "农业", ("农业", "养殖", "种业", "农牧", "生猪")),
    ("media", "传媒游戏", ("传媒", "游戏", "影视", "动漫", "文化传媒")),
    ("internet", "互联网", ("互联网", "电商", "云计算", "数字经济")),
    ("finance", "金融", ("银行", "券商", "证券公司", "证券行业", "保险", "金融服务", "金融科技")),
    ("real_estate", "地产", ("地产", "房地产", "物业")),
    (
        "resources",
        "资源周期",
        ("煤炭", "有色", "钢铁", "化工", "石油", "资源", "黄金", "能源", "新材料", "稀土"),
    ),
    ("environment", "环保", ("环保", "碳中和", "低碳", "绿色")),
    ("infrastructure", "基建", ("基建", "建筑", "建材")),
    (
        "manufacturing",
        "高端制造",
        ("机器人", "高端制造", "智能制造", "装备", "工程机械", "汽车", "工业", "机械"),
    ),
    (
        "tech",
        "科技TMT",
        ("科技", "计算机", "软件", "电子", "通信", "5G", "信息技术", "信息产业", "TMT"),
    ),
    (
        "broad_index",
        "宽基指数",
        (
            "沪深300", "中证500", "上证50", "中证A500", "中证1000", "创业板", "科创50",
            "科创板50", "深证100", "A50", "中证A50", "全指", "综合指数",
        ),
    ),
]

SECTOR_LABELS: dict[str, str] = {key: label for key, label, _ in SECTOR_RULES}
SECTOR_ORDER: list[str] = [key for key, _, _ in SECTOR_RULES]

# 全称里的样板词：几乎所有基金全称都含"证券投资基金"，
# 若不剥离，"证券"会命中金融板块，把全库都误判成金融。
_GENERIC_TOKENS = ("证券投资基金", "基金管理", "股份有限公司", "有限公司")


def detect_sector(
    name: str | None, full_name: str | None = None, tracking_index: str | None = None
) -> str | None:
    """按优先级返回第一个命中的板块 key；无命中返回 None。"""
    corpus = " ".join(part for part in (name, full_name, tracking_index) if part)
    if not corpus:
        return None
    for token in _GENERIC_TOKENS:
        corpus = corpus.replace(token, " ")
    for key, _label, keywords in SECTOR_RULES:
        if any(word in corpus for word in keywords):
            return key
    return None
