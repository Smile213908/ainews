"""统一 HTTP 客户端（技术选型 §6.1）：UA 池、每源最小间隔限流、超时纪律、错误分类。"""

import asyncio
import random
import time

import httpx

from app.collectors.base import CollectorError

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

DEFAULT_TIMEOUT = httpx.Timeout(15.0)


class HttpClient:
    """每个 collector 持有一个实例，按源独立限流。"""

    def __init__(self, source: str, rate_limit: float = 5.0) -> None:
        self.source = source
        self.rate_limit = rate_limit
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
                headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            )
        return self._client

    async def _throttle(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.rate_limit:
                await asyncio.sleep(self.rate_limit - elapsed)
            self._last_request_at = time.monotonic()

    async def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
    ) -> httpx.Response:
        await self._throttle()
        client = await self._get_client()
        merged_headers = {"User-Agent": random.choice(USER_AGENTS)}
        if headers:
            merged_headers.update(headers)
        try:
            resp = await client.get(
                url, params=params, headers=merged_headers, cookies=cookies
            )
        except httpx.TimeoutException as e:
            raise CollectorError(f"[{self.source}] 请求超时: {url}") from e
        except httpx.HTTPError as e:
            raise CollectorError(f"[{self.source}] 网络错误: {e}") from e
        if resp.status_code != 200:
            raise CollectorError(
                f"[{self.source}] HTTP {resp.status_code}: {url}"
            )
        return resp

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
