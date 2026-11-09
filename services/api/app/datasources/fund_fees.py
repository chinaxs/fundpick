"""公开申购/赎回费率表；仅解析明确区间和金额，未知语义不填零。"""

import re
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

SOURCE = "https://fundf10.eastmoney.com/jjfl_{code}.html"


def parse_fee_page(html: str) -> list[dict[str, str]]:
    """保留费率原文及标准/天天基金优惠来源；排除管理/托管等已计净值的费用。"""
    soup = BeautifulSoup(html, "html.parser")
    rules = []
    for heading in soup.select("h4.t"):
        title = heading.get_text(strip=True)
        if title == "交易确认日":
            table = heading.find_next("table")
            if table:
                confirmation_cells = [
                    cell.get_text(strip=True) for cell in table.find_all(["th", "td"])
                ]
                for index, cell in enumerate(confirmation_cells[:-1]):
                    if cell in {"买入确认日", "卖出确认日"}:
                        rules.append(
                            {
                                "kind": "confirmation",
                                "condition": cell,
                                "standard": confirmation_cells[index + 1],
                                "discounted": "",
                            }
                        )
            continue
        kind = "buy" if title == "申购费率（前端）" else "sell" if title == "赎回费率" else None
        if not kind:
            continue
        table = heading.find_next("table")
        if table is None:
            continue
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) != 2:
                continue  # 有其他限定条件时不得猜测
            parts = re.split(r"\|", cells[1].get_text(" ", strip=True))
            rules.append(
                {
                    "kind": kind,
                    "condition": cells[0].get_text(strip=True),
                    "standard": parts[0].strip(),
                    "discounted": parts[-1].strip() if len(parts) == 2 else "",
                }
            )
    return rules


def fetch_fee_rules(code: str) -> list[dict[str, str]]:
    """有超时的单基金公开费率查询，调用方在线程中执行。"""
    request = Request(SOURCE.format(code=code), headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=8) as response:
        return parse_fee_page(response.read().decode("utf-8"))
