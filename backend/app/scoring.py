"""热度与重要性评分——全局唯一口径（R-401 / R-402 / R-403）。

热度公式只在这里定义一份，落库时预计算进 hot_score / importance_rank 列，
列表接口直接 ORDER BY，前端展示使用后端返回的归一化分值，消灭 1.0 的双份公式。
"""

import math

# 重要性排序权重：urgent 最前（R-402）
IMPORTANCE_ORDER: dict[str, int] = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

IMPORTANCE_LEVELS = tuple(IMPORTANCE_ORDER.keys())

# 归一化热度标签阈值（R-403）：由归一化分值驱动前端的 爆/热/温 标签
HOT_LEVELS = {"爆": 80, "热": 50, "温": 0}

# 归一化参考刻度：原始热度分达到该值时归一化为 100
_NORMALIZE_SCALE = 1e6


def calc_hot_score(
    like_count: int | None = None,
    retweet_count: int | None = None,
    view_count: int | None = None,
) -> float:
    """热度分 = 点赞×10 + 转发×5 + log10(浏览)×2（R-401）。"""
    likes = like_count or 0
    retweets = retweet_count or 0
    views = max(view_count or 1, 1)
    return likes * 10 + retweets * 5 + math.log10(views) * 2


def importance_rank(importance: str) -> int:
    """重要性 → 排序权重（urgent=0 … low=3），未知值按 low 处理。"""
    return IMPORTANCE_ORDER.get(importance, IMPORTANCE_ORDER["low"])


def normalize_hot_score(score: float) -> int:
    """原始热度分 → 0–100 归一化分值（对数刻度，R-403）。"""
    if score <= 0:
        return 0
    normalized = 100 * math.log10(1 + score) / math.log10(1 + _NORMALIZE_SCALE)
    return min(100, round(normalized))


def hot_level(score: float) -> str:
    """归一化分值 → 热度等级标签（爆/热/温）。"""
    n = normalize_hot_score(score)
    if n >= HOT_LEVELS["爆"]:
        return "爆"
    if n >= HOT_LEVELS["热"]:
        return "热"
    return "温"
