"""搜狗采集器：HTML 爬虫（技术选型 §6.4：相对链接补全、广告位过滤）。"""

from selectolax.parser import HTMLParser

from app.collectors.base import SearchResult, SelectorDriftError
from app.collectors.http import HttpClient

SEARCH_URL = "https://www.sogou.com/web"


class SogouCollector:
    name = "sogou"
    rate_limit = 5.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    def parse(self, html: str, *, limit: int = 10) -> list[SearchResult]:
        tree = HTMLParser(html)
        items = tree.css("div.results > div") or tree.css("div.rb")
        if not items:
            raise SelectorDriftError(f"[{self.name}] 结果容器选择器未命中，页面结构可能已变更")
        results: list[SearchResult] = []
        for item in items:
            if len(results) >= limit:
                break
            # 广告位过滤：带广告标识的节点跳过
            if item.css_first("[data-ad-type]") or "广告" in (item.attributes.get("class") or ""):
                continue
            title_node = item.css_first("h3 a")
            if not title_node:
                continue
            url = title_node.attributes.get("href") or ""
            if url.startswith("/"):
                url = f"https://www.sogou.com{url}"  # 相对链接补全
            if not url:
                continue
            snippet_node = item.css_first(".str_info") or item.css_first(".ft")
            results.append(
                SearchResult(
                    title=title_node.text(strip=True),
                    url=url,
                    source=self.name,
                    content=snippet_node.text(strip=True) if snippet_node else "",
                )
            )
        if not results:
            raise SelectorDriftError(f"[{self.name}] 未提取到有效结果（可能全是广告或结构变更）")
        return results

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        resp = await self._http.get(SEARCH_URL, params={"query": query})
        return self.parse(resp.text, limit=limit)
