"""按消费方切分 OpenAPI 文档。

后端同时服务两类调用方：门户（匿名只读）与后台（需登录）。
全量 `/docs` 把 30 个接口堆在一个列表里，联调时要在长列表里翻找，
还容易误调受限接口。这里按路径前缀切出两份独立文档：

- `/docs/portal`：门户接口（对外，可公开）
- `/docs/admin`：后台接口（对内）

仍然只有一个 FastAPI 应用、一套路由，只是文档视图不同。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocGroup:
    """一份独立文档的定义。"""

    key: str
    """URL 片段：/docs/{key} 与 /openapi/{key}.json"""

    prefix: str
    """接口路径前缀，用于从全量 schema 中筛选。"""

    title: str
    description: str


DOC_GROUPS: tuple[DocGroup, ...] = (
    DocGroup(
        key="portal",
        prefix="/api/v1/portal",
        title="Study 门户 API",
        description=(
            "门户网站消费的公开接口。**全部匿名可访问、只读、可公开缓存。**\n\n"
            "前端对应 `apps/portal`；后台接口见 [/docs/admin](/docs/admin)。"
        ),
    ),
    DocGroup(
        key="admin",
        prefix="/api/v1/admin",
        title="Study 后台 API",
        description=(
            "后台管理接口。除登录与刷新令牌外，均需 `Authorization: Bearer <token>`，"
            "用户管理另需超管权限。\n\n"
            "前端对应 `apps/admin`；门户接口见 [/docs/portal](/docs/portal)。"
        ),
    ),
)


def build_subset_schema(full: dict[str, Any], group: DocGroup) -> dict[str, Any]:
    """从完整 schema 截取指定前缀的接口，生成可独立渲染的文档。"""
    schema = deepcopy(full)

    paths = {
        path: item for path, item in full.get("paths", {}).items() if path.startswith(group.prefix)
    }

    info = dict(schema.get("info", {}))
    info["title"] = group.title
    info["description"] = group.description
    schema["info"] = info
    schema["paths"] = paths

    # 只保留被实际引用的 tag，否则 Swagger 侧栏会列出空分组
    used: set[str] = set()
    for operations in paths.values():
        for operation in operations.values():
            if isinstance(operation, dict):
                used.update(operation.get("tags", []))
    if "tags" in schema:
        schema["tags"] = [tag for tag in schema["tags"] if tag.get("name") in used]

    return schema
