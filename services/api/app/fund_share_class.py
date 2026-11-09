"""基金份额类别识别。

同一只基金常有 A/C/E 等份额，费率与销售渠道不同，收益却几乎一样。
排行里混在一起会让人误以为"同一个产品出现了三次"，所以单独拆出
基础名称与类别，前端可以把它们标出来、也可以按需折叠。

规则刻意保守：
- 只认**结尾单个字母**，可带"类/份额"或括号；
- 该字母前面的文字必须以中文结尾，避免把 "沪深300ETF" 拆成 "…ET" + "F"；
- 基础名称至少两个字且含中文，避免整个名字都是字母时误判。
"""

from __future__ import annotations

import re

# 常见份额类别：A/B/C/D/E/H/I/R/Y，也兼容 F/N 等平台自定义类别
_CLASS_LETTERS = "ABCDEFHIJLMNOPRSTUY"
_PATTERN = re.compile(
    rf"^(?P<base>.+?)\s*[（(]?\s*(?P<cls>[{_CLASS_LETTERS}])(?:类|份额)?\s*[）)]?$"
)


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def split_share_class(name: str | None) -> tuple[str, str | None]:
    """把 "华夏成长混合A" 拆成 ("华夏成长混合", "A")。

    无法判断时返回 (原名称, None)，不做猜测。
    """
    if not name:
        return "", None
    original = name.strip()
    match = _PATTERN.match(original)
    if not match:
        return original, None
    base = match.group("base").rstrip(" （(-·")
    cls = match.group("cls")
    if len(base) < 2 or not _has_cjk(base):
        return original, None
    # A/B/C 前面必须紧跟中文（或右括号），否则多半是 ETF、LOF 之类的英文后缀
    if not _has_cjk(base[-1]) and base[-1] not in "）)】":
        return original, None
    return base, cls


def share_class_label(name: str | None) -> str | None:
    """给前端展示用的短标签，如 "A 类"。"""
    _, cls = split_share_class(name)
    return f"{cls} 类" if cls else None


__all__ = ["share_class_label", "split_share_class"]
