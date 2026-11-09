"""通用小工具。"""

import re
import unicodedata
import uuid


def slugify(text: str, max_length: int = 120) -> str:
    """生成 URL 友好的 slug。

    非 ASCII 字符（中文等）无法直接转写时，退化为随机短码，避免生成一长串百分号编码。
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if not slug:
        slug = f"post-{uuid.uuid4().hex[:8]}"
    return slug[:max_length].strip("-")
