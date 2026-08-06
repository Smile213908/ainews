"""AI 分析编排（技术选型 §7.3）：

- 内容哈希缓存（30 天，跨关键词复用，R-206）；
- Semaphore 限流并发；
- 失败进重试队列（最多 2 次，R-205）——不放行也不丢弃。
"""

import asyncio
import hashlib

import structlog

from app.ai.provider import AIError, AIProvider
from app.ai.schemas import AIAnalysis
from app.collectors.base import SearchResult
from app.core.redis import cache_get, cache_set

log = structlog.get_logger()

CACHE_TTL = 30 * 24 * 3600  # 30 天
MAX_RETRIES = 2


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AnalyzedItem:
    def __init__(self, item: SearchResult, analysis: AIAnalysis, from_cache: bool) -> None:
        self.item = item
        self.analysis = analysis
        self.from_cache = from_cache


class RetryQueue:
    """AI 失败重试队列（进程内 + 可演进 Redis list）。条目: (item, keyword, attempts)。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[SearchResult, str, int]] = asyncio.Queue()

    async def push(self, item: SearchResult, keyword: str, attempts: int) -> None:
        if attempts < MAX_RETRIES:
            await self._queue.put((item, keyword, attempts + 1))
        else:
            log.warning("ai_retry_exhausted_drop", url=item.url, keyword=keyword)

    async def drain(self) -> list[tuple[SearchResult, str, int]]:
        items: list[tuple[SearchResult, str, int]] = []
        while not self._queue.empty():
            items.append(await self._queue.get())
        return items


class AIAnalyzer:
    def __init__(self, provider: AIProvider, concurrency: int = 3) -> None:
        self.provider = provider
        self.semaphore = asyncio.Semaphore(concurrency)
        self.retry_queue = RetryQueue()
        self.stats = {"calls": 0, "cache_hits": 0, "failures": 0}

    async def _analyze_one(
        self, item: SearchResult, keyword: str, prematch: list[str]
    ) -> AnalyzedItem | None:
        key = f"ai:analysis:{content_hash(item.content or item.title)}"
        cached = await cache_get(key)
        if cached:
            self.stats["cache_hits"] += 1
            return AnalyzedItem(item, AIAnalysis.model_validate(cached), from_cache=True)

        async with self.semaphore:
            try:
                analysis = await self.provider.analyze(
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    keyword=keyword,
                    prematch=prematch,
                )
            except AIError as e:
                self.stats["failures"] += 1
                log.warning("ai_analyze_failed", url=item.url, error=str(e))
                await self.retry_queue.push(item, keyword, attempts=0)
                return None
        self.stats["calls"] += 1
        await cache_set(key, analysis.model_dump(), CACHE_TTL)
        return AnalyzedItem(item, analysis, from_cache=False)

    async def analyze_batch(
        self, items: list[SearchResult], keyword: str, prematch: list[str]
    ) -> list[AnalyzedItem]:
        results = await asyncio.gather(
            *(self._analyze_one(item, keyword, prematch) for item in items)
        )
        return [r for r in results if r is not None]
