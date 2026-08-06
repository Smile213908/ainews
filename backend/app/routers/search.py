"""全网搜索（FR-3.1，同步版）：Twitter + Bing 聚合，前 10 条附 AI 分析，不落库。

M4 将改造为异步任务（FR-3.2）：返回 task_id + WS/轮询获取结果。
"""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.analysis import AIAnalyzer
from app.ai.provider import get_provider
from app.collectors.base import CollectorError, SearchResult, SourceUnavailable
from app.collectors.bing import BingCollector
from app.collectors.twitter import TwitterCollector
from app.pipeline.cleaning import clean
from app.pipeline.settings_repo import get_setting_int

router = APIRouter(prefix="/search", tags=["search"])

SEARCH_ANALYZE_LIMIT = 10  # 前 10 条附 AI 分析（FR-3.1）


class SearchRequest(BaseModel):
    query: str


class SearchResultItem(BaseModel):
    title: str
    url: str
    source: str
    content: str
    author_name: str | None = None
    author_verified: bool = False
    # AI 分析（未分析/降级时为空或默认值）
    is_real: bool | None = None
    relevance: int | None = None
    importance: str | None = None
    summary: str | None = None
    ai_reviewed: bool = False


@router.post("", response_model=list[SearchResultItem])
async def search(body: SearchRequest) -> list[SearchResultItem]:
    query = body.query.strip()
    if not query:
        return []

    collectors = [TwitterCollector(), BingCollector()]

    async def run_one(c) -> list[SearchResult]:
        try:
            return await c.search(query)
        except (CollectorError, SourceUnavailable):
            return []
        except Exception:  # noqa: BLE001
            return []

    batches = await asyncio.gather(*(run_one(c) for c in collectors))
    merged = clean([item for batch in batches for item in batch])

    # 前 10 条送 AI 分析（搜索结果不落库）
    provider = get_provider()
    analyzer = AIAnalyzer(provider, concurrency=get_setting_int("ai_concurrency") or 3)
    analyzed = await analyzer.analyze_batch(merged[:SEARCH_ANALYZE_LIMIT], query, [])
    by_url = {a.item.url: a for a in analyzed}

    out: list[SearchResultItem] = []
    for item in merged:
        a = by_url.get(item.url)
        out.append(
            SearchResultItem(
                title=item.title,
                url=item.url,
                source=item.source,
                content=item.content[:500],
                author_name=item.author_name,
                author_verified=item.author_verified,
                is_real=a.analysis.is_real if a else None,
                relevance=a.analysis.relevance if a else None,
                importance=a.analysis.importance if a else None,
                summary=a.analysis.summary if a else None,
                ai_reviewed=a is not None,
            )
        )
    return out
