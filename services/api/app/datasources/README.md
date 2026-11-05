# 数据源（datasources）

把外部数据接入的差异关在这里，业务层只依赖协议。

## 边界
- 负责：调用第三方接口、字段映射、脏数据清洗（空值/NaN/日期格式）、限速。
- 不负责：业务规则、入库逻辑（在 `scripts/`）、HTTP 接口。

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `base.py` | `FundDataProvider` 协议 + 数据类（`FundBasic` / `FundSnapshot` / `RiskMetric` / `NavPoint`）+ `RANK_CATEGORIES` |
| `akshare_source.py` | AkShare 实现；`_to_float` / `_to_date` 负责清洗 |
| `__init__.py` | `get_provider()` 工厂，换源只改这里 |

## 扩展方式
新增数据源（如 Wind）：

```python
class WindProvider:
    name = "wind"

    def list_funds(self) -> list[FundBasic]: ...
    def list_snapshots(self, category: str) -> list[FundSnapshot]: ...
    def nav_history(self, code: str) -> list[NavPoint]: ...
    def risk_metrics(self, code: str) -> list[RiskMetric]: ...
```

然后在 `get_provider()` 里按配置切换。**不要在采集脚本里直接 import akshare。**

## 清洗规则（血泪教训）
- pandas 的 `NaT` 是 `datetime` 子类，必须先按字符串判空；
- `float('nan')` 不能入库，统一 `to_num()` 转 `None`；
- 百分比字符串（`"0.15%"`）去掉 `%` 再转 float；
- 中文列名用 `getattr(row, "字段名")` 读取（pandas `itertuples` 支持）。

## 依赖
上游：无 ｜ 下游：`scripts/sync_funds.py`
