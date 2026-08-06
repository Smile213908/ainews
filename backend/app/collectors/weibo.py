"""微博采集器：热搜榜匹配（R-107）。

拉取实时热搜榜，与关键词做双向包含匹配——是"监控"而非"搜索"。
"""

from app.collectors.base import CollectorError, SearchResult
from app.collectors.http import HttpClient

HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch"


class WeiboHotSearchCollector:
    name = "weibo"
    rate_limit = 3.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        resp = await self._http.get(HOT_SEARCH_URL)
        try:
            data = resp.json()
            realtime = data["data"]["realtime"]
        except Exception as e:
            raise CollectorError(f"[{self.name}] 热搜榜解析失败: {e}") from e

        q = query.lower()
        results: list[SearchResult] = []
        for item in realtime:
            word = item.get("word") or ""
            # 双向包含匹配（R-107）
            if q not in word.lower() and word.lower() not in q:
                continue
            results.append(
                SearchResult(
                    title=word,
                    url=f"https://s.weibo.com/weibo?q=%23{word}%23",
                    source=self.name,
                    source_id=str(item.get("rank", "")),
                    content=item.get("note") or word,
                    view_count=item.get("raw_hot"),  # 热搜热度值
                    raw_payload=item,
                )
            )
            if len(results) >= limit:
                break
        return results
