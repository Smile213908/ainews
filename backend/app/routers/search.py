"""全网搜索（FR-3）：异步任务化。

- POST /api/search：提交即返回 task_id（≤1s，FR-3.2）；
- GET /api/search/{task_id}：轮询任务状态与结果（WS 同时广播 task:update）；
- 搜索范围 Twitter + Bing，前 10 条附 AI 分析，结果不落库（FR-3.1）。
"""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.analysis import AIAnalyzer
from app.ai.provider import get_provider
from app.collectors.base import CollectorError, SearchResult, SourceUnavailable
from app.collectors.bing import BingCollector
from app.collectors.twitter import TwitterCollector
from app.pipeline import search_tasks
from app.pipeline.cleaning import clean
from app.pipeline.settings_repo import get_setting_int

router = APIRouter(prefix="/search", tags=["search"])

SEARCH_ANALYZE_LIMIT = 10  # 前 10 条附 AI 分析（FR-3.1）


class SearchRequest(BaseModel):
    query: str


class SearchSubmitResponse(BaseModel):
    task_id: str
    status: str


class SearchTaskStatus(BaseModel):
    task_id: str
    status: str  # queued/running/completed/failed
    result: list[dict] | None = None
    error: str | None = None


class SearchResultItem(BaseModel):
    title: str
    url: str
    source: str
    content: str
    author_name: str | None = None
    author_verified: bool = False
    is_real: bool | None = None
    relevance: int | None = None
    importance: str | None = None
    summary: str | None = None
    ai_reviewed: bool = False


async def execute_search(query: str) -> list[dict]:
    """搜索执行体：聚合采集 → 清洗 → 前 10 条 AI 分析。供任务管理器调用。"""
    collectors = [TwitterCollector(), BingCollector()]

    async def run_one(c) -> list[SearchResult]:
        try:
            return await c.search(query)
        except (CollectorError, SourceUnavailable):
            return []
        except Exception:
            return []

    batches = await asyncio.gather(*(run_one(c) for c in collectors))
    merged = clean([item for batch in batches for item in batch])

    provider = get_provider()
    analyzer = AIAnalyzer(provider, concurrency=get_setting_int("ai_concurrency") or 3)
    analyzed = await analyzer.analyze_batch(merged[:SEARCH_ANALYZE_LIMIT], query, [])
    by_url = {a.item.url: a for a in analyzed}

    out: list[dict] = []
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
            ).model_dump()
        )
    return out


@router.post("", response_model=SearchSubmitResponse, status_code=202)
async def submit_search(body: SearchRequest) -> SearchSubmitResponse:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="搜索词不能为空")
    task = search_tasks.submit(query, execute_search)
    return SearchSubmitResponse(task_id=task.id, status=task.status)


@router.get("/{task_id}", response_model=SearchTaskStatus)
async def get_search_task(task_id: str) -> SearchTaskStatus:
    task = search_tasks.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return SearchTaskStatus(
        task_id=task.id, status=task.status, result=task.result, error=task.error
    )
