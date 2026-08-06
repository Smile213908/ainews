"""采集器基座（重构方案 §4.3）：Collector Protocol + 统一结果模型 + 异常分类。

新增一个数据源 = 新增一个文件 + 在 registry 注册一行。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class SearchResult:
    """采集层统一输出，字段与 Hotspot 模型一一对应。"""

    title: str
    url: str
    source: str
    content: str = ""
    source_id: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None
    retweet_count: int | None = None
    reply_count: int | None = None
    comment_count: int | None = None
    quote_count: int | None = None
    danmaku_count: int | None = None
    author_name: str | None = None
    author_avatar: str | None = None
    author_verified: bool = False
    raw_payload: dict[str, Any] | None = field(default=None)


class CollectorError(Exception):
    """采集器通用错误（网络/状态码/限流等）。"""


class SourceUnavailable(CollectorError):
    """源未配置凭据或不可用（如 Twitter 缺 API Key）——不算故障，不参与告警。"""


class SelectorDriftError(CollectorError):
    """页面结构变更导致选择器失效——显式抛出而非静默返回空（1.0 教训）。"""


class Collector(Protocol):
    name: str
    rate_limit: float  # 最小请求间隔（秒）

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        """按查询词检索，返回统一结果列表。失败抛 CollectorError 及其子类。"""
        ...
