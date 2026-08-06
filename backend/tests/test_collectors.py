"""采集器测试：解析 fixture + 选择器漂移显式报错（respx mock HTTP）。"""

import pytest
import respx
from httpx import Response

from app.collectors.base import SelectorDriftError, SourceUnavailable
from app.collectors.bing import BingCollector
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.sogou import SogouCollector
from app.collectors.twitter import TwitterCollector
from app.collectors.weibo import WeiboHotSearchCollector

BING_HTML = """
<html><body><ol id="b_results">
  <li class="b_algo"><h2><a href="https://example.com/a">Kimi 发布新版本</a></h2>
    <div class="b_caption"><p>Kimi 今日发布...</p></div></li>
  <li class="b_algo"><h2><a href="https://example.com/b">AI 行业动态</a></h2></li>
</ol></body></html>
"""

SOGOU_HTML = """
<html><body><div class="results">
  <div><h3><a href="/link?url=abc">搜狗结果一</a></h3><div class="str_info">摘要一</div></div>
  <div data-ad-type="1"><h3><a href="https://ad.com">广告位</a></h3></div>
  <div><h3><a href="https://example.com/c">搜狗结果二</a></h3></div>
</div></body></html>
"""


def test_bing_parse_fixture():
    results = BingCollector().parse(BING_HTML)
    assert len(results) == 2
    assert results[0].title == "Kimi 发布新版本"
    assert results[0].source == "bing"


def test_bing_selector_drift_raises():
    with pytest.raises(SelectorDriftError):
        BingCollector().parse("<html><body><div>页面改版了</div></body></html>")


def test_sogou_parse_relative_url_and_ad_filter():
    results = SogouCollector().parse(SOGOU_HTML)
    urls = [r.url for r in results]
    assert "https://ad.com" not in urls  # 广告位过滤
    assert "https://www.sogou.com/link?url=abc" in urls  # 相对链接补全


def test_twitter_tweet_quality_filter():
    collector = TwitterCollector()
    base = {
        "text": "DeepSeek 新模型太强了",
        "url": "https://x.com/a/status/1",
        "likeCount": 5,  # 低于阈值
        "author": {"name": "user", "isBlueVerified": False},
    }
    assert collector._parse_tweet(base) is None  # 普通账号低互动被过滤
    base["author"]["isBlueVerified"] = True
    assert collector._parse_tweet(base) is None  # 蓝 V 阈值 10，5 仍不够
    base["likeCount"] = 15
    assert collector._parse_tweet(base) is not None  # 蓝 V 达标


def test_twitter_unavailable_without_key():
    collector = TwitterCollector()
    with pytest.raises(SourceUnavailable):
        collector._key()


@pytest.mark.asyncio
async def test_hackernews_search():
    payload = {
        "hits": [
            {
                "objectID": "123",
                "title": "DeepSeek releases new model",
                "url": "https://example.com/ds",
                "points": 200,
                "num_comments": 80,
                "author": "hnuser",
                "created_at_i": 1786000000,
            }
        ]
    }
    with respx.mock:
        respx.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=Response(200, json=payload)
        )
        results = await HackerNewsCollector().search("DeepSeek")
    assert len(results) == 1
    assert results[0].like_count == 200
    assert results[0].source == "hackernews"


@pytest.mark.asyncio
async def test_weibo_hot_search_match():
    payload = {
        "data": {
            "realtime": [
                {"word": "Kimi 新功能上线", "rank": 3, "raw_hot": 123456},
                {"word": "无关热搜", "rank": 5},
            ]
        }
    }
    with respx.mock:
        respx.get("https://weibo.com/ajax/side/hotSearch").mock(
            return_value=Response(200, json=payload)
        )
        results = await WeiboHotSearchCollector().search("Kimi")
    assert len(results) == 1
    assert "Kimi" in results[0].title  # 双向包含匹配（R-107）
