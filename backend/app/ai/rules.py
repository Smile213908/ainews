"""过滤规则（R-204）：三级过滤，阈值做成可调参数（可 AB）。"""

from app.ai.schemas import DEFAULT_RELEVANCE_FLOOR, DEFAULT_UNMENTIONED_FLOOR, AIAnalysis


def passes_threshold(
    analysis: AIAnalysis,
    *,
    relevance_floor: int = DEFAULT_RELEVANCE_FLOOR,
    unmentioned_floor: int = DEFAULT_UNMENTIONED_FLOOR,
) -> bool:
    """① isReal=false 丢弃；② relevance<50 丢弃；③ 未直接提及且 relevance<65 丢弃。"""
    if not analysis.is_real:
        return False
    if analysis.relevance < relevance_floor:
        return False
    if analysis.keyword_mentioned is False and analysis.relevance < unmentioned_floor:
        return False
    return True
