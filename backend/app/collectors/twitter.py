"""Twitter 采集器：twitterapi.io 第三方 API（技术选型 §6.4）。

- 高级搜索语法（min_faves / -filter:retweets）；
- Top + Latest 双轨拉取后合并去重；
- 本地质量过滤：低互动过滤，蓝 V 账号阈值减半；
- 未配置 TWITTER_API_KEY 时抛 SourceUnavailable（不算故障，不告警）。
"""

from datetime import UTC, datetime

from app.collectors.base import SearchResult, SourceUnavailable
from app.collectors.http import HttpClient
from app.config import get_settings

SEARCH_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"

MIN_LIKES = 20
MIN_LIKES_VERIFIED = 10  # 蓝 V 阈值减半


class TwitterCollector:
    name = "twitter"
    rate_limit = 3.0

    def __init__(self) -> None:
        self._http = HttpClient(self.name, self.rate_limit)

    def _key(self) -> str:
        key = get_settings().twitter_api_key
        if not key:
            raise SourceUnavailable(f"[{self.name}] 未配置 TWITTER_API_KEY，跳过该源")
        return key

    @staticmethod
    def _parse_tweet(t: dict) -> SearchResult | None:
        text = t.get("text") or ""
        url = t.get("url") or ""
        if not text or not url:
            return None
        author = t.get("author") or {}
        created = t.get("createdAt")
        published = None
        if created:
            try:
                published = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            except ValueError:
                published = None
        likes = t.get("likeCount") or 0
        verified = bool(author.get("isBlueVerified"))
        threshold = MIN_LIKES_VERIFIED if verified else MIN_LIKES
        if likes < threshold:
            return None
        return SearchResult(
            title=text[:100],
            content=text,
            url=url,
            source="twitter",
            source_id=t.get("id"),
            published_at=published or datetime.now(UTC),
            view_count=t.get("viewCount"),
            like_count=likes,
            retweet_count=t.get("retweetCount"),
            reply_count=t.get("replyCount"),
            quote_count=t.get("quoteCount"),
            author_name=author.get("name") or author.get("userName"),
            author_avatar=author.get("profilePicture"),
            author_verified=verified,
            raw_payload=t,
        )

    async def _search_once(self, query: str, query_type: str) -> list[SearchResult]:
        resp = await self._http.get(
            SEARCH_URL,
            params={"query": query, "queryType": query_type},
            headers={"X-API-Key": self._key()},
        )
        data = resp.json()
        tweets = data.get("tweets") or []
        out: list[SearchResult] = []
        for t in tweets:
            parsed = self._parse_tweet(t)
            if parsed:
                out.append(parsed)
        return out

    async def search(self, query: str, *, limit: int = 15) -> list[SearchResult]:
        q = f"{query} min_faves:{MIN_LIKES} -filter:retweets"
        # Top + Latest 双轨
        top = await self._search_once(q, "Top")
        latest = await self._search_once(q, "Latest")
        seen: set[str] = set()
        merged: list[SearchResult] = []
        for item in [*top, *latest]:
            if item.url in seen:
                continue
            seen.add(item.url)
            merged.append(item)
            if len(merged) >= limit:
                break
        return merged
