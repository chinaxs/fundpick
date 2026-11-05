# API 层（路由与依赖）

对外暴露 HTTP 接口，只做"翻译"：HTTP 语义 ↔ 业务调用。

## 目录结构（按调用方划分）

```
app/api/
├── deps.py              共用依赖：SessionDep / CurrentUser / SuperUser / RequestIdDep
└── v1/
    ├── router.py        汇总三组路由
    ├── common/          公共：探活（无鉴权）
    │   └── health.py
    ├── portal/          门户：匿名只读
    │   ├── funds.py
    │   ├── stats.py
    │   └── articles.py
    └── admin/           后台：需登录
        ├── auth.py
        ├── users.py
        ├── articles.py
        ├── funds.py
        └── ai.py
```

**目录即归属**：新增接口先判断"谁在调用"，再放进对应包。
前缀在包的 `__init__.py` 里统一加（`/portal`、`/admin`），子文件只写自己的相对路径。

## 边界

- 负责：参数解析与校验、鉴权依赖、调用 service、包装 `ApiResponse`、声明 `response_model`。
- 不负责：SQL、事务、业务规则、跨模块编排。

## 分组规则

| 包 | 前缀 | 鉴权 | 允许的操作 |
| --- | --- | --- | --- |
| `common/` | `/health` | 无 | 只读探针 |
| `portal/` | `/portal` | 无 | **只读**，不得引入 `CurrentUser` |
| `admin/` | `/admin` | 必须有 | 读写，可含敏感数据 |

`portal/` 里出现写操作、或 `admin/` 里出现无鉴权端点，都视为**设计错误**，评审时应直接打回。

## 扩展方式

新增一个资源：

1. 判断归属，在 `portal/` 或 `admin/` 下建文件；
2. `router = APIRouter(prefix="/xxx", tags=["后台 · XXX"])`；
3. 在对应包的 `__init__.py` 里 `include_router`；
4. 新 tag 同步登记到 `app/main.py` 的 `OPENAPI_TAGS`（否则 Swagger 分组缺描述）。

权限用依赖表达（`SuperUser`），**不要**在函数体里写 `if 用户是管理员 then ...`。
查询参数用 `Query(...)` 声明约束，响应统一 `ApiResponse[T]`。

## 文档

按分组切成两份，见 `app/core/openapi.py`：

| 地址 | 范围 |
| --- | --- |
| `/docs/portal` | `/portal/**` |
| `/docs/admin` | `/admin/**` |
| `/docs` | 全量（排查跨端问题时用） |

新分组的 tag 要登记到 `app/main.py` 的 `OPENAPI_TAGS`，否则 Swagger 里缺描述。

## 依赖

上游：`schemas`、`services`、`core` ｜ 下游：无（最外层）
