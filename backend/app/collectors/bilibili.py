"""B 站采集器：热门榜 + 全站排行榜匹配（R-107 模式）。

2026 年起 x/web-interface/search/type 搜索 API 被风控拦截（重定向到
aba.bilibili.com 出错页，WBI 签名 + 真实 buvid 均无效，需登录态）。
改为与微博一致的"榜单匹配"：拉取热门榜 + 全站排行榜，与关键词做双向
包含匹配（标题/简介/分区/UP 主名）。原 UP 主账号检测（R-104）随搜索
API 失效一并下线。
"""

import asyncio
from datetime import UTC, datetime

from app.collectors.base import CollectorError, SearchResult
from app.collectors.http import HttpClient

POPULAR_URL = "https://api.bilibili.com/x/web-interface/popular"
RANKING_URL = "https://api.bilibili.com/x/web-interface/ranking/v2"
SPI_URL = "https://api.bilibili.com/x/frontend/finger/spi"

_HEADERS = {"Referer": "https://www.bilibili.com"}


def _bili_time(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=UTC) if ts else None


def _to_result(v: dict, source_name: str) -> SearchResult:
    stat = v.get("stat") or {}
    owner = v.get("owner") or {}
    return SearchResult(
        title=v.get("title") or "",
        url=f"https://www.bilibili.com/video/{v.get('bvid')}",
        source=source_name,
        source_id=v.get("bvid"),
        content=v.get("desc") or v.get("title") or "",
        published_at=_bili_time(v.get("pubdate")),
        view_count=stat.get("view"),
        like_count=stat.get("like"),
        comment_count=stat.get("reply"),
        danmaku_count=stat.get("danmaku"),
        author_name=owner.get("name"),
        raw_payload=v,
    )


def _matches(v: dict, q: str) -> bool:
    """双向包含匹配：标题 / 简介 / 分区 / UP 主名。"""
    haystacks = [
        v.get("title") or "",
        v.get("desc") or "",
        v.get("tname") or "",
        (v.get("owner") or {}).get("name") or "",
    ]
    ql = q.lower()
    return any(ql in h.lower() or h.lower() in ql for h in haystacks if h)


class BilibiliCollector:
    name = "bilibili"
    rate_limit = 3.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)
        self._cookies: dict[str, str] | None = None

    async def _ensure_cookies(self) -> dict[str, str]:
        """buvid3/buvid4 预热：无 cookie 请求榜单接口会被风控（code=-352）。"""
        if self._cookies is None:
            resp = await self._http.get(SPI_URL, headers=_HEADERS)
            data = resp.json()["data"]
            self._cookies = {"buvid3": data["b_3"], "buvid4": data["b_4"]}
        return self._cookies

    async def _fetch_list(self, url: str, params: dict) -> list[dict]:
        cookies = await self._ensure_cookies()
        resp = await self._http.get(url, params=params, headers=_HEADERS, cookies=cookies)
        try:
            data = resp.json()
        except Exception as e:
            raise CollectorError(f"[{self.name}] 响应非 JSON: {e}") from e
        if data.get("code") != 0:
            raise CollectorError(
                f"[{self.name}] API code={data.get('code')}: {data.get('message')}"
            )
        return (data.get("data") or {}).get("list") or []

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        # 热门榜（50 条）+ 全站排行榜（100 条），按 bvid 去重后匹配关键词
        popular, ranking = await asyncio.gather(
            self._fetch_list(POPULAR_URL, {"ps": 50, "pn": 1}),
            self._fetch_list(RANKING_URL, {"rid": 0, "type": "all"}),
        )
        seen: set[str] = set()
        results: list[SearchResult] = []
        for v in [*popular, *ranking]:
            bvid = v.get("bvid")
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            if not _matches(v, query):
                continue
            results.append(_to_result(v, self.name))
            if len(results) >= limit:
                break
        return results
