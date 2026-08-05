"""SQLModel 数据模型（重构方案 §3.1）。

改进点（相对 1.0）：
- Hotspot 增加预计算列 hot_score / importance_rank，消灭全表内存排序（R-401/R-402）；
- 信息流复合索引 ix_hotspot_feed；
- raw_payload 留存原始报文（PG 上用 JSONB，本地 SQLite 退化为普通 JSON）；
- Notification 补真正的外键；
- 新增 SourceHealth 源健康表（FR-6）；
- Keyword/Hotspot 预留 owner_id（多用户 backlog，2.0 不做 UI）。
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON as SA_JSON
from sqlalchemy import Column, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

try:  # PostgreSQL 上使用 JSONB，其他方言退化为 JSON
    from sqlalchemy.dialects.postgresql import JSONB

    RawPayloadType = SA_JSON().with_variant(JSONB, "postgresql")
except Exception:  # pragma: no cover
    RawPayloadType = SA_JSON()


def utcnow() -> datetime:
    return datetime.now(UTC)


class Keyword(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    text: str = Field(unique=True, index=True, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool = True
    owner_id: UUID | None = None  # 预留：多用户 backlog
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    hotspots: list["Hotspot"] = Relationship(back_populates="keyword")


class Hotspot(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("url", "source", name="uq_hotspot_url_source"),
        Index("ix_hotspot_feed", "created_at", "importance_rank", "hot_score"),
        Index("ix_hotspot_published_at", "published_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    title: str = Field(max_length=500)
    content: str = ""
    url: str = Field(max_length=1000)
    source: str = Field(index=True, max_length=50)  # twitter/bing/hackernews/sogou/bilibili/weibo
    source_id: str | None = Field(default=None, max_length=200)

    # AI 分析结果（R-203）
    is_real: bool = True
    relevance: int = Field(default=0, ge=0, le=100)
    relevance_reason: str | None = None
    keyword_mentioned: bool | None = None
    importance: str = Field(default="low", max_length=20)  # low/medium/high/urgent
    summary: str | None = None
    ai_reviewed: bool = True  # False 表示未经 AI 审核的降级数据（R-207）

    # 预计算列：写入时由 scoring.py 算好（R-401/R-402）
    hot_score: float = 0.0
    importance_rank: int = 3

    # 互动指标
    view_count: int | None = None
    like_count: int | None = None
    retweet_count: int | None = None
    reply_count: int | None = None
    comment_count: int | None = None
    quote_count: int | None = None
    danmaku_count: int | None = None

    # 作者信息
    author_name: str | None = Field(default=None, max_length=200)
    author_avatar: str | None = Field(default=None, max_length=1000)
    author_verified: bool = False

    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)

    keyword_id: UUID | None = Field(default=None, foreign_key="keyword.id")
    keyword: Keyword | None = Relationship(back_populates="hotspots")

    # 原始报文留存，便于排查与重分析
    raw_payload: dict | None = Field(default=None, sa_column=Column(RawPayloadType, nullable=True))

    owner_id: UUID | None = None  # 预留：多用户 backlog


class Notification(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    type: str = Field(max_length=20)  # hotspot / alert
    title: str = Field(max_length=500)
    content: str = ""
    is_read: bool = False
    created_at: datetime = Field(default_factory=utcnow, index=True)

    hotspot_id: UUID | None = Field(default=None, foreign_key="hotspot.id")
    hotspot: Hotspot | None = Relationship()


class Setting(SQLModel, table=True):
    """运行时配置 KV 表：检查周期、AI 配额、邮件阈值等（FR-7.2）。"""

    key: str = Field(primary_key=True, max_length=100)
    value: str = ""
    updated_at: datetime = Field(default_factory=utcnow)


class SourceHealth(SQLModel, table=True):
    """数据源健康记录（FR-6）：连续失败 ≥3 触发 alert 通知（R-303）。"""

    source: str = Field(primary_key=True, max_length=50)
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    alert_open: bool = False  # True 表示告警未恢复，用于告警去重（FR-6.2）
