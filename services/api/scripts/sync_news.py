"""资讯快讯同步 CLI（后台「同步资讯」按钮调用）。

与 `scripts/sync_funds.py` 共用 `sync_jobs` 任务表：子进程执行、结果文件回填状态，
API 重启后也能恢复。刻意不复用同一个脚本，是因为它结尾会 dispose_engine()
并且参数语义都是基金采集，混在一起只会让两边都难维护。

    python -m scripts.sync_news --limit 20
    python -m scripts.sync_news --job-id 12      # 后台触发
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, setup_logging
from app.db.session import async_session_factory, dispose_engine
from app.job_progress import JobProgress, SyncCancelled
from app.models.article import Article, ArticleStatus
from app.news_sources import collect_all

logger = get_logger(__name__)
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
STARTED_AT = time.time()
PROGRESS = JobProgress(None)


async def sync_news(session: AsyncSession, limit_per_source: int = 20) -> dict[str, int]:
    """采集 → 按指纹去重 → 写入草稿。

    同步进来的文章 status=draft 且 content 为空：只做摘编，
    发布与补充原创正文都由后台人工完成。
    """
    items = await asyncio.to_thread(collect_all, limit_per_source)
    PROGRESS.begin("news", len(items))
    ids = [item.external_id for item in items]

    existing_ids: set[str] = set()
    existing_slugs: set[str] = set()
    if ids:
        rows = (
            await session.execute(select(Article.external_id).where(Article.external_id.in_(ids)))
        ).scalars()
        existing_ids = set(rows)
        candidates = [f"news-{item.external_id[:16]}" for item in items]
        slug_rows = (
            await session.execute(select(Article.slug).where(Article.slug.in_(candidates)))
        ).scalars()
        existing_slugs = set(slug_rows)

    created = 0
    for item in items:
        PROGRESS.checkpoint()
        if item.external_id in existing_ids:
            PROGRESS.advance(skipped=1)
            continue

        slug = f"news-{item.external_id[:16]}"
        if slug in existing_slugs:
            suffix = 2
            while f"{slug}-{suffix}" in existing_slugs:
                suffix += 1
            slug = f"{slug}-{suffix}"
        existing_slugs.add(slug)

        session.add(
            Article(
                title=item.title,
                slug=slug,
                summary=item.summary,
                content=None,
                status=ArticleStatus.DRAFT,
                category=item.category,
                source=item.source,
                source_name=item.source_name,
                source_url=item.url,
                origin="sync",
                external_id=item.external_id,
            )
        )
        created += 1
        PROGRESS.advance(ok=1)

    await session.commit()
    return {
        "fetched": len(items),
        "created": created,
        "skipped": len(items) - created,
    }


def _write_job_result(job_id: int | None, status: str, message: str) -> None:
    """与 sync_funds 一致的结果文件格式，供 SyncJobService._reconcile 读取。"""
    if job_id is None:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_ms": int((time.time() - STARTED_AT) * 1000),
        "message": message[:500],
        "counts": {
            "phase": PROGRESS.phase,
            "total": PROGRESS.total,
            "succeeded": PROGRESS.succeeded,
            "failed": PROGRESS.failed,
            "skipped": PROGRESS.skipped,
            "failures": PROGRESS.failures,
        },
    }
    try:
        (LOG_DIR / f"sync_job_{job_id}.result.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:  # pragma: no cover
        logger.warning("[任务] 写入结果文件失败: %s", exc)


async def run(limit_per_source: int) -> dict[str, int]:
    async with async_session_factory() as session:
        result: dict[str, Any] = await sync_news(session, limit_per_source)
    await dispose_engine()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="资讯快讯同步")
    # 参数与 sync_funds 保持一致：SyncJobService.spawn 用同一套命令行
    parser.add_argument("--mode", default="news")
    parser.add_argument("--limit", type=int, default=20, help="每个来源最多取几条")
    parser.add_argument("--codes", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--job-id", type=int, default=None)
    args = parser.parse_args()

    global PROGRESS
    PROGRESS = JobProgress(args.job_id)

    setup_logging()
    logger.info("开始同步资讯，每源 %d 条", args.limit)
    try:
        stats = asyncio.run(run(args.limit))
    except SyncCancelled:
        logger.info("收到取消请求，本轮资讯同步已停止")
        _write_job_result(args.job_id, "cancelled", "已按请求取消")
        return
    except Exception as exc:
        logger.exception("资讯同步失败: %s", exc)
        _write_job_result(args.job_id, "failed", str(exc))
        raise SystemExit(1) from exc

    message = (
        f"取回 {stats['fetched']} 条，新增 {stats['created']} 篇草稿，"
        f"跳过 {stats['skipped']} 条重复"
    )
    logger.info("资讯同步完成：%s", message)
    _write_job_result(args.job_id, "success", message)


if __name__ == "__main__":
    main()
