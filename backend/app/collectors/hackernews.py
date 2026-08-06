"""HackerNews 采集器：Algolia 官方 API，最稳定的源（技术选型 §6.4）。"""

from datetime import UTC, datetime

from app.collectors.base import CollectorError, SearchResult
from app.collectors.http import HttpClient

API_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsCollector:
    name = "hackernews"
    rate_limit = 2.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        resp = await self._http.get(
            API_URL,
            params={
                "query": query,
                "tags": "story",
                "hitsPerPage": min(limit, 50),
                # 限定最近 24h（R-105 新鲜度前置）
                "numericFilters": f"created_at_i>{int(datetime.now(UTC).timestamp()) - 86400}",
            },
        )
        try:
            data = resp.json()
            hits = data["hits"]
        except Exception as e:
            raise CollectorError(f"[{self.name}] 响应解析失败: {e}") from e

        results: list[SearchResult] = []
        for hit in hits[:limit]:
            title = hit.get("title") or ""
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            if not title:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    source=self.name,
                    source_id=str(hit.get("objectID", "")),
                    content=hit.get("story_text") or title,
                    published_at=(
                        datetime.fromtimestamp(hit["created_at_i"], tz=UTC)
                        if hit.get("created_at_i")
                        else None
                    ),
                    like_count=hit.get("points"),
                    comment_count=hit.get("num_comments"),
                    author_name=hit.get("author"),
                    raw_payload=hit,
                )
            )
        return results
