"""微博采集器：热搜榜匹配（R-107）。

拉取实时热搜榜，与关键词做双向包含匹配——是"监控"而非"搜索"。
注意：weibo.com 对无 Referer 的请求直接 403，必须带 Referer + Accept。
"""

from app.collectors.base import CollectorError, SearchResult
from app.collectors.http import HttpClient

HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch"
# 反爬必需头：缺失 Referer 返回 403 Forbidden
_HEADERS = {
    "Referer": "https://weibo.com/",
    "Accept": "application/json, text/plain, */*",
}


class WeiboHotSearchCollector:
    name = "weibo"
    rate_limit = 3.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        resp = await self._http.get(HOT_SEARCH_URL, headers=_HEADERS)
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
                    # 热搜热度值（num 为现行字段，raw_hot 为旧字段兜底）
                    view_count=item.get("num") or item.get("raw_hot"),
                    raw_payload=item,
                )
            )
            if len(results) >= limit:
                break
        return results
