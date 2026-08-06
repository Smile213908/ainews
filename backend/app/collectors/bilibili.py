"""B 站采集器：公开搜索 API + UP 主账号检测（R-104）。

- 随机 buvid3 cookie 规避 412 风控；
- search_type=bili_user 做账号检测：精确匹配（或粉丝 >1000 且名称包含）时
  直接拉取该 UP 主最新视频（x/space/arc/search）。
"""

import random
import uuid
from datetime import UTC, datetime

from app.collectors.base import CollectorError, SearchResult
from app.collectors.http import HttpClient

SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
USER_VIDEOS_URL = "https://api.bilibili.com/x/space/arc/search"


def _buvid3() -> str:
    return f"{uuid.uuid4()}{random.randint(10000, 99999)}infoc"


def _bili_time(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=UTC) if ts else None


class BilibiliCollector:
    name = "bilibili"
    rate_limit = 3.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    async def _get(self, url: str, params: dict) -> dict:
        resp = await self._http.get(
            url,
            params=params,
            cookies={"buvid3": _buvid3()},
            headers={"Referer": "https://www.bilibili.com"},
        )
        try:
            data = resp.json()
        except Exception as e:
            raise CollectorError(f"[{self.name}] 响应非 JSON: {e}") from e
        if data.get("code") != 0:
            raise CollectorError(
                f"[{self.name}] API code={data.get('code')}: {data.get('message')}"
            )
        return data

    async def detect_account(self, keyword: str) -> dict | None:
        """R-104：关键词精确匹配 UP 主名，或粉丝 >1000 且名称包含关键词。"""
        data = await self._get(
            SEARCH_URL, params={"search_type": "bili_user", "keyword": keyword}
        )
        for user in (data.get("data") or {}).get("result") or []:
            uname = (user.get("uname") or "").replace('<em class="keyword">', "").replace(
                "</em>", ""
            )
            fans = user.get("fans") or 0
            if uname == keyword or (fans > 1000 and keyword.lower() in uname.lower()):
                return {"mid": user["mid"], "uname": uname, "fans": fans}
        return None

    async def user_videos(self, mid: int, *, limit: int = 10) -> list[SearchResult]:
        data = await self._get(
            USER_VIDEOS_URL,
            params={"mid": mid, "ps": min(limit, 30), "order": "pubdate"},
        )
        vlist = ((data.get("data") or {}).get("list") or {}).get("vlist") or []
        results: list[SearchResult] = []
        for v in vlist[:limit]:
            results.append(
                SearchResult(
                    title=v.get("title") or "",
                    url=f"https://www.bilibili.com/video/{v.get('bvid')}",
                    source=self.name,
                    source_id=v.get("bvid"),
                    content=v.get("description") or v.get("title") or "",
                    published_at=_bili_time(v.get("created")),
                    view_count=v.get("play"),
                    like_count=v.get("like"),
                    comment_count=v.get("comment"),
                    danmaku_count=v.get("video_review"),
                    author_name=v.get("author"),
                    raw_payload=v,
                )
            )
        return results

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        # 账号检测优先（R-104）：命中 UP 主则拉取其最新视频
        account = await self.detect_account(query)
        if account:
            return await self.user_videos(account["mid"], limit=limit)

        data = await self._get(
            SEARCH_URL, params={"search_type": "video", "keyword": query, "order": "pubdate"}
        )
        items = (data.get("data") or {}).get("result") or []
        results: list[SearchResult] = []
        for v in items[:limit]:
            title = (v.get("title") or "").replace('<em class="keyword">', "").replace(
                "</em>", ""
            )
            results.append(
                SearchResult(
                    title=title,
                    url=v.get("arcurl") or f"https://www.bilibili.com/video/{v.get('bvid')}",
                    source=self.name,
                    source_id=v.get("bvid"),
                    content=v.get("description") or title,
                    published_at=_bili_time(v.get("pubdate")),
                    view_count=v.get("play") if isinstance(v.get("play"), int) else None,
                    like_count=v.get("like"),
                    comment_count=v.get("review"),
                    danmaku_count=v.get("danmaku"),
                    author_name=v.get("author"),
                    raw_payload=v,
                )
            )
        return results
