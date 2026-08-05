"""API 请求/响应 schema（Pydantic v2）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, computed_field

from app.scoring import hot_level, normalize_hot_score


# ---------- Keyword ----------
class KeywordCreate(BaseModel):
    text: str
    category: str | None = None


class KeywordUpdate(BaseModel):
    text: str | None = None
    category: str | None = None


class KeywordRead(BaseModel):
    id: UUID
    text: str
    category: str | None
    is_active: bool
    created_at: datetime
    hotspot_count: int = 0


# ---------- Hotspot ----------
class HotspotRead(BaseModel):
    id: UUID
    title: str
    content: str
    url: str
    source: str
    is_real: bool
    relevance: int
    relevance_reason: str | None
    keyword_mentioned: bool | None
    importance: str
    summary: str | None
    ai_reviewed: bool
    hot_score: float
    view_count: int | None
    like_count: int | None
    retweet_count: int | None
    reply_count: int | None
    comment_count: int | None
    danmaku_count: int | None
    author_name: str | None
    author_avatar: str | None
    author_verified: bool
    published_at: datetime | None
    created_at: datetime
    keyword_id: UUID | None
    keyword_text: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def hot_score_normalized(self) -> int:
        """归一化热度分 0–100（R-403）：前端展示与标签的唯一数据源。"""
        return normalize_hot_score(self.hot_score)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def hot_level(self) -> str:
        """热度等级标签（爆/热/温），由后端分值驱动。"""
        return hot_level(self.hot_score)


class HotspotPage(BaseModel):
    items: list[HotspotRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class HotspotStats(BaseModel):
    total: int
    today_new: int
    urgent_count: int
    by_source: dict[str, int]


# ---------- Notification ----------
class NotificationRead(BaseModel):
    id: UUID
    type: str
    title: str
    content: str
    is_read: bool
    created_at: datetime
    hotspot_id: UUID | None


# ---------- SourceHealth ----------
class SourceHealthRead(BaseModel):
    source: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    alert_open: bool
