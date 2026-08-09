"""一次性数据迁移脚本：1.0 SQLite（Prisma schema）→ 2.0 新库（重构方案 §3.3）。

- 逐表迁移 Keyword / Hotspot / Notification；
- 迁移时对存量热点回填 hot_score / importance_rank（R-401/R-402）；
- 原 SQLite 文件只读，不修改；建议迁移前自行备份。

用法：
    uv run python scripts/migrate_sqlite_to_pg.py \
        --source "sqlite:////path/to/1.0/dev.db" \
        --target "postgresql+psycopg://user:pass@host:5432/monitor"

不传 --target 时默认使用当前 DATABASE_URL。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: F401  注册表
from app.config import get_settings
from app.models import Hotspot, Keyword, Notification
from app.scoring import calc_hot_score, importance_rank


def _parse_dt(value: object) -> datetime | None:
    """兼容 Prisma SQLite 的多种时间存储形态（ISO 字符串 / 毫秒时间戳 / None）。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return datetime.fromtimestamp(int(s) / 1000, tz=UTC)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def migrate(source_url: str, target_url: str, dry_run: bool = False) -> None:
    src = create_engine(source_url)
    dst = create_engine(target_url)

    if not dry_run:
        SQLModel.metadata.create_all(dst)

    stats = {"keywords": 0, "hotspots": 0, "notifications": 0, "skipped": 0}

    with src.connect() as sc, Session(dst) as ds:
        # ---- Keyword ----
        kw_id_map: dict[str, UUID] = {}
        for row in sc.execute(text('SELECT * FROM "Keyword"')).mappings():
            old_id = str(row["id"])
            new_kw = Keyword(
                id=_to_uuid(old_id) or Keyword().id,
                text=str(row["text"]),
                category=row.get("category"),
                is_active=bool(row.get("isActive", True)),
                created_at=_parse_dt(row.get("createdAt")) or datetime.now(UTC),
                updated_at=_parse_dt(row.get("updatedAt")) or datetime.now(UTC),
            )
            kw_id_map[old_id] = new_kw.id
            if not dry_run:
                ds.merge(new_kw)
            stats["keywords"] += 1

        # ---- Hotspot（回填预计算列） ----
        for row in sc.execute(text('SELECT * FROM "Hotspot"')).mappings():
            importance = str(row.get("importance") or "low")
        if importance not in ("low", "medium", "high", "urgent"):
            importance = "low"
            new_hs = Hotspot(
                id=_to_uuid(row["id"]) or Hotspot().id,
                title=str(row.get("title") or "")[:500],
                content=str(row.get("content") or ""),
                url=str(row.get("url") or "")[:1000],
                source=str(row.get("source") or "unknown")[:50],
                source_id=row.get("sourceId"),
                is_real=bool(row.get("isReal", True)),
                relevance=max(0, min(100, int(row.get("relevance") or 0))),
                relevance_reason=row.get("relevanceReason"),
                keyword_mentioned=row.get("keywordMentioned"),
                importance=importance,
                summary=row.get("summary"),
                view_count=row.get("viewCount"),
                like_count=row.get("likeCount"),
                retweet_count=row.get("retweetCount"),
                reply_count=row.get("replyCount"),
                comment_count=row.get("commentCount"),
                quote_count=row.get("quoteCount"),
                danmaku_count=row.get("danmakuCount"),
                author_name=row.get("authorName"),
                author_avatar=row.get("authorAvatar"),
                author_verified=bool(row.get("authorVerified", False)),
                published_at=_parse_dt(row.get("publishedAt")),
                created_at=_parse_dt(row.get("createdAt")) or datetime.now(UTC),
                keyword_id=kw_id_map.get(str(row.get("keywordId"))),
                raw_payload=json.loads(row["rawPayload"]) if row.get("rawPayload") else None,
            )
            # 回填预计算列（R-401/R-402）
            new_hs.hot_score = calc_hot_score(
                new_hs.like_count, new_hs.retweet_count, new_hs.view_count
            )
            new_hs.importance_rank = importance_rank(new_hs.importance)
            if not dry_run:
                ds.merge(new_hs)
            stats["hotspots"] += 1

        # ---- Notification ----
        for row in sc.execute(text('SELECT * FROM "Notification"')).mappings():
            new_n = Notification(
                id=_to_uuid(row["id"]) or Notification().id,
                type=str(row.get("type") or "hotspot")[:20],
                title=str(row.get("title") or "")[:500],
                content=str(row.get("content") or ""),
                is_read=bool(row.get("isRead", False)),
                created_at=_parse_dt(row.get("createdAt")) or datetime.now(UTC),
                hotspot_id=_to_uuid(row.get("hotspotId")),
            )
            if not dry_run:
                ds.merge(new_n)
            stats["notifications"] += 1

        if not dry_run:
            ds.commit()

        # ---- 抽验：目标库行数 ----
        check = {
            "keywords_in_target": len(ds.exec(select(Keyword)).all()),
            "hotspots_in_target": len(ds.exec(select(Hotspot)).all()),
            "notifications_in_target": len(ds.exec(select(Notification)).all()),
        }

    print("迁移统计:", stats)
    print("目标库行数:", check)
    if dry_run:
        print("（dry-run，未写入）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="1.0 SQLite → 2.0 新库迁移")
    parser.add_argument("--source", required=True, help="1.0 的 SQLite URL，如 sqlite:////path/dev.db")
    parser.add_argument("--target", default=None, help="目标库 URL，默认取 DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入")
    args = parser.parse_args()

    target = args.target or get_settings().database_url
    migrate(args.source, target, dry_run=args.dry_run)
