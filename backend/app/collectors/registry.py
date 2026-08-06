"""采集器注册表（重构方案 §4.3）：新增一个源 = 新增一个文件 + 注册一行。

来源优先级（R-106）：Twitter > 微博 > B 站 > HN > 搜狗 > Bing
"""

from app.collectors.base import Collector
from app.collectors.bilibili import BilibiliCollector
from app.collectors.bing import BingCollector
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.sogou import SogouCollector
from app.collectors.twitter import TwitterCollector
from app.collectors.weibo import WeiboHotSearchCollector

REGISTRY: dict[str, Collector] = {
    "twitter": TwitterCollector(),
    "weibo": WeiboHotSearchCollector(),
    "bilibili": BilibiliCollector(),
    "hackernews": HackerNewsCollector(),
    "sogou": SogouCollector(),
    "bing": BingCollector(),
}

# R-106 优先级序（决定配额分配顺序）
SOURCE_PRIORITY: list[str] = [
    "twitter",
    "weibo",
    "bilibili",
    "hackernews",
    "sogou",
    "bing",
]


def enabled() -> list[Collector]:
    return [REGISTRY[name] for name in SOURCE_PRIORITY if name in REGISTRY]
