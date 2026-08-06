"""配额前置（Stage 6，R-202）：先截断候选数量再送 AI——AI 调用量硬上限。

Twitter ≤ twitter_quota 条/关键词/轮，其他源合计 ≤ other_quota 条。
配额按来源优先级（R-106）分配。
"""

from app.collectors.base import SearchResult

DEFAULT_TWITTER_QUOTA = 15
DEFAULT_OTHER_QUOTA = 10


def apply_quota(
    candidates: list[SearchResult],
    *,
    twitter_quota: int = DEFAULT_TWITTER_QUOTA,
    other_quota: int = DEFAULT_OTHER_QUOTA,
) -> list[SearchResult]:
    twitter_items = [c for c in candidates if c.source == "twitter"]
    other_items = [c for c in candidates if c.source != "twitter"]
    return twitter_items[:twitter_quota] + other_items[:other_quota]
