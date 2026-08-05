"""热点信息流（FR-2）。

- 全部排序走数据库 ORDER BY + 真分页（FR-2.5），修复 1.0 全表内存排序；
- 筛选：来源/重要性/关键词/时间范围/真实性（FR-2.4）；
- 统计：累计、今日新增、urgent 数、按来源分布（FR-2.1）。
"""

from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, func, select

from app.db import get_session
from app.models import Hotspot
from app.schemas import HotspotPage, HotspotRead, HotspotStats

router = APIRouter(prefix="/hotspots", tags=["hotspots"])

_SORTS = ("latest", "published", "relevance", "importance", "hot")

_TIME_RANGES = {
    "1h": timedelta(hours=1),
    "today": None,  # 特殊处理：当天 0 点
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _time_floor(range_: str | None) -> datetime | None:
    if not range_:
        return None
    now = datetime.now(UTC)
    if range_ == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = _TIME_RANGES.get(range_)
    return now - delta if delta else None


def _to_read(hs: Hotspot) -> HotspotRead:
    return HotspotRead(
        id=hs.id,
        title=hs.title,
        content=hs.content,
        url=hs.url,
        source=hs.source,
        is_real=hs.is_real,
        relevance=hs.relevance,
        relevance_reason=hs.relevance_reason,
        keyword_mentioned=hs.keyword_mentioned,
        importance=hs.importance,
        summary=hs.summary,
        ai_reviewed=hs.ai_reviewed,
        hot_score=hs.hot_score,
        view_count=hs.view_count,
        like_count=hs.like_count,
        retweet_count=hs.retweet_count,
        reply_count=hs.reply_count,
        comment_count=hs.comment_count,
        danmaku_count=hs.danmaku_count,
        author_name=hs.author_name,
        author_avatar=hs.author_avatar,
        author_verified=hs.author_verified,
        published_at=hs.published_at,
        created_at=hs.created_at,
        keyword_id=hs.keyword_id,
        keyword_text=hs.keyword.text if hs.keyword else None,
    )


@router.get("", response_model=HotspotPage)
def list_hotspots(
    source: str | None = None,
    importance: str | None = None,
    keyword_id: UUID | None = None,
    range_: str | None = Query(default=None, alias="range"),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    is_real: bool | None = None,
    sort: str = Query(default="latest", pattern="^(latest|published|relevance|importance|hot)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> HotspotPage:
    stmt = select(Hotspot)

    if source:
        stmt = stmt.where(Hotspot.source == source)
    if importance:
        stmt = stmt.where(Hotspot.importance == importance)
    if keyword_id:
        stmt = stmt.where(Hotspot.keyword_id == keyword_id)
    if is_real is not None:
        stmt = stmt.where(Hotspot.is_real == is_real)

    floor = _time_floor(range_)
    if floor:
        stmt = stmt.where(Hotspot.created_at >= floor)
    if from_:
        stmt = stmt.where(Hotspot.created_at >= from_)
    if to:
        stmt = stmt.where(Hotspot.created_at <= to)

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()

    if sort == "latest":
        stmt = stmt.order_by(col(Hotspot.created_at).desc())
    elif sort == "published":
        stmt = stmt.order_by(col(Hotspot.published_at).desc().nulls_last())
    elif sort == "relevance":
        stmt = stmt.order_by(col(Hotspot.relevance).desc(), col(Hotspot.created_at).desc())
    elif sort == "importance":
        # R-402：urgent > high > medium > low，同级按时间倒序
        stmt = stmt.order_by(col(Hotspot.importance_rank).asc(), col(Hotspot.created_at).desc())
    elif sort == "hot":
        stmt = stmt.order_by(col(Hotspot.hot_score).desc())

    items = session.exec(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    return HotspotPage(
        items=[_to_read(hs) for hs in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/stats", response_model=HotspotStats)
def hotspot_stats(session: Session = Depends(get_session)) -> HotspotStats:
    total = session.exec(select(func.count()).select_from(Hotspot)).one()
    today_floor = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = session.exec(
        select(func.count()).select_from(Hotspot).where(Hotspot.created_at >= today_floor)
    ).one()
    urgent = session.exec(
        select(func.count()).select_from(Hotspot).where(Hotspot.importance == "urgent")
    ).one()
    by_source_rows = session.exec(
        select(Hotspot.source, func.count()).group_by(col(Hotspot.source))
    ).all()
    return HotspotStats(
        total=total,
        today_new=today_new,
        urgent_count=urgent,
        by_source={str(src): cnt for src, cnt in by_source_rows},
    )


@router.delete("/{hotspot_id}", status_code=204)
def delete_hotspot(hotspot_id: UUID, session: Session = Depends(get_session)) -> None:
    hs = session.get(Hotspot, hotspot_id)
    if not hs:
        raise HTTPException(status_code=404, detail="热点不存在")
    session.delete(hs)  # 关联通知的 hotspot_id 由外键置空，不报错（FR-2.7）
    session.commit()
