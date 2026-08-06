"""清洗阶段（Stage 4）：去重 → 新鲜度 → 优先级（R-105/R-106）。纯函数，可单测。"""

from datetime import UTC, datetime, timedelta

from app.collectors.base import SearchResult
from app.collectors.registry import SOURCE_PRIORITY

MAX_AGE = timedelta(days=7)  # R-105


def dedupe(items: list[SearchResult]) -> list[SearchResult]:
    """批内去重：(url, source) 唯一。"""
    seen: set[tuple[str, str]] = set()
    out: list[SearchResult] = []
    for item in items:
        key = (item.url, item.source)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def filter_freshness(items: list[SearchResult]) -> list[SearchResult]:
    """发布时间超过 7 天的丢弃；无发布时间的放行（R-105）。"""
    floor = datetime.now(UTC) - MAX_AGE
    out: list[SearchResult] = []
    for item in items:
        if item.published_at is None:
            out.append(item)
            continue
        published = item.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if published >= floor:
            out.append(item)
    return out


def prioritize(items: list[SearchResult]) -> list[SearchResult]:
    """按来源优先级排序（R-106）：Twitter > 微博 > B 站 > HN > 搜狗 > Bing。"""
    order = {name: i for i, name in enumerate(SOURCE_PRIORITY)}
    return sorted(items, key=lambda x: order.get(x.source, len(order)))


def clean(items: list[SearchResult]) -> list[SearchResult]:
    return prioritize(filter_freshness(dedupe(items)))
