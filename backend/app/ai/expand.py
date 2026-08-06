"""查询扩展（R-201）：AI 扩展 5–15 个变体，缓存 7 天；AI 不可用退化为规则法。"""

import structlog

from app.ai.provider import AIError, AIProvider, rule_based_expand
from app.core.redis import cache_get, cache_set

log = structlog.get_logger()

EXPAND_CACHE_TTL = 7 * 24 * 3600  # 7 天


async def expand_query(keyword: str, provider: AIProvider) -> list[str]:
    key = f"ai:expand:{keyword}"
    cached = await cache_get(key)
    if cached:
        return list(cached)

    try:
        variants = await provider.expand_query(keyword)
    except AIError as e:
        log.warning("query_expand_fallback_rules", keyword=keyword, error=str(e))
        variants = rule_based_expand(keyword)

    if keyword not in variants:
        variants.insert(0, keyword)
    await cache_set(key, variants, EXPAND_CACHE_TTL)
    return variants


def prematch_variants(title: str, content: str, variants: list[str]) -> list[str]:
    """文本预匹配：返回命中的变体（两阶段检索架构的中间层）。"""
    haystack = f"{title} {content}".lower()
    return [v for v in variants if v.lower() in haystack]
