"""基金搜索的关键词处理：分词、拼音、板块名映射。

为什么不直接在库里 `LIKE '%关键字%'`：
中文用户搜基金有三种习惯——输入几个字（"华夏成长"）、输入全拼或首字母
（"huaxia"、"hxcz"）、或者按主题（"半导体"）。第三种基金名里往往没有这个词，
靠 `name LIKE` 永远搜不到。

这里把"用户可能怎么输"收敛成两个派生列（全拼、首字母）+ 一张板块映射表，
由仓储层统一拼接条件；本模块只做纯函数，方便单测。
"""

from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin

from app.fund_sectors import SECTOR_LABELS

# 拼音列只保留小写字母与数字：括号、连字符留着会让 "LOF" 之类难以匹配
_PUNCT = re.compile(r"[^a-z0-9]+")

# 一次最多取几个关键词：再多也不会更精确，只会把 SQL 拖慢
MAX_TOKENS = 4

_SECTOR_BY_LABEL: dict[str, str] = {label: key for key, label in SECTOR_LABELS.items()}


def pinyin_index(name: str) -> tuple[str, str]:
    """返回 (全拼, 首字母)，均为小写、无分隔。

    >>> pinyin_index("华夏成长混合")
    ('huaxiachengzhanghunhe', 'hxczhh')
    >>> pinyin_index("易方达沪深300ETF联接A")
    ('yifangdahushen300etflianjiea', 'yfdhs300etflja')
    """
    if not name.strip():
        return "", ""

    # 首字母直接用 pypinyin 的 FIRST_LETTER 模式：它会把 ASCII 片段
    # （ETF、300）原样保留，正好符合 "hs300" 这类输入习惯。
    full = _PUNCT.sub("", "".join(lazy_pinyin(name)).lower())
    initials = _PUNCT.sub("", "".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).lower())
    return full, initials


def search_tokens(keyword: str | None) -> list[str]:
    """按空白拆分关键词，去重并限制个数。

    多关键词之间是"且"的关系：输入 "华夏 混合" 只会留下名字里同时含这两个词的基金，
    比把整串当一个短语更符合搜索直觉。
    """
    if not keyword:
        return []
    seen: list[str] = []
    for token in keyword.split():
        cleaned = token.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:MAX_TOKENS]


def sector_code_for(token: str) -> str | None:
    """把中文板块名映射成板块 key，如 "新能源" -> "new_energy"。"""
    return _SECTOR_BY_LABEL.get(token.strip())
