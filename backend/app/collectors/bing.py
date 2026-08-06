"""Bing 采集器：HTML 爬虫（selectolax 解析，技术选型 §6.2/§6.4）。

选择器失效时抛 SelectorDriftError——显式告警而非静默返回空。
"""

from selectolax.parser import HTMLParser

from app.collectors.base import SearchResult, SelectorDriftError
from app.collectors.http import HttpClient

SEARCH_URL = "https://www.bing.com/search"


class BingCollector:
    name = "bing"
    rate_limit = 5.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    def parse(self, html: str, *, limit: int = 10) -> list[SearchResult]:
        tree = HTMLParser(html)
        items = tree.css("li.b_algo")
        if not items:
            raise SelectorDriftError(f"[{self.name}] 选择器 li.b_algo 未命中，页面结构可能已变更")
        results: list[SearchResult] = []
        for item in items[:limit]:
            title_node = item.css_first("h2 a")
            if not title_node:
                continue
            url = title_node.attributes.get("href") or ""
            if not url.startswith("http"):
                continue
            snippet_node = item.css_first(".b_caption p") or item.css_first("p")
            results.append(
                SearchResult(
                    title=title_node.text(strip=True),
                    url=url,
                    source=self.name,
                    content=snippet_node.text(strip=True) if snippet_node else "",
                )
            )
        if not results:
            raise SelectorDriftError(f"[{self.name}] li.b_algo 内未提取到有效结果")
        return results

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        resp = await self._http.get(SEARCH_URL, params={"q": query, "count": limit * 2})
        return self.parse(resp.text, limit=limit)
