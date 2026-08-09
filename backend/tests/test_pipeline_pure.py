"""pipeline 纯函数测试：清洗（R-105/106）、配额（R-202）、阈值（R-204）、扩展降级（R-201）。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.ai.expand import prematch_variants
from app.ai.provider import AIError, OpenAICompatProvider, rule_based_expand
from app.ai.rules import passes_threshold
from app.ai.schemas import AIAnalysis
from app.collectors.base import SearchResult
from app.pipeline.cleaning import dedupe, filter_freshness, prioritize
from app.pipeline.quota import apply_quota


def _mk(url: str, source: str = "bing", **kw) -> SearchResult:
    return SearchResult(title="t", url=url, source=source, **kw)


# ---------- 清洗 ----------
def test_dedupe_by_url_source():
    items = [_mk("https://a.com/1", "bing"), _mk("https://a.com/1", "bing"),
             _mk("https://a.com/1", "sogou")]  # 同 url 不同源保留
    out = dedupe(items)
    assert len(out) == 2


def test_freshness_7d_rule():
    old = _mk("https://a.com/old", published_at=datetime.now(UTC) - timedelta(days=8))
    new = _mk("https://a.com/new", published_at=datetime.now(UTC) - timedelta(days=1))
    no_time = _mk("https://a.com/notime")  # 无发布时间放行（R-105）
    out = filter_freshness([old, new, no_time])
    urls = [i.url for i in out]
    assert "https://a.com/old" not in urls
    assert set(urls) == {"https://a.com/new", "https://a.com/notime"}


def test_prioritize_source_order():
    items = [_mk("https://x/1", "bing"), _mk("https://x/2", "twitter"),
             _mk("https://x/3", "weibo"), _mk("https://x/4", "hackernews")]
    out = prioritize(items)
    assert [i.source for i in out] == ["twitter", "weibo", "hackernews", "bing"]  # R-106


# ---------- 配额前置 ----------
def test_quota_hard_cap():
    twitter = [_mk(f"https://t.com/{i}", "twitter") for i in range(20)]
    others = [_mk(f"https://o.com/{i}", "bing") for i in range(15)]
    out = apply_quota(twitter + others, twitter_quota=15, other_quota=10)
    assert len([i for i in out if i.source == "twitter"]) == 15
    assert len([i for i in out if i.source != "twitter"]) == 10
    assert len(out) == 25  # AI 调用硬上限（R-202）


# ---------- 三级过滤 ----------
def test_threshold_rules():
    assert not passes_threshold(AIAnalysis(is_real=False, relevance=90, keyword_mentioned=True))
    assert not passes_threshold(AIAnalysis(relevance=49, keyword_mentioned=True))
    assert passes_threshold(AIAnalysis(relevance=50, keyword_mentioned=True))
    # 未提及关键词需 ≥65（防同领域沾边）
    assert not passes_threshold(AIAnalysis(relevance=60, keyword_mentioned=False))
    assert passes_threshold(AIAnalysis(relevance=65, keyword_mentioned=False))


# ---------- 查询扩展降级 ----------
def test_rule_based_expand():
    variants = rule_based_expand("AI Agent")
    assert "AI Agent" in variants
    assert "AI" in variants
    assert "AI-Agent" in variants or "AI Agent" in variants
    assert len(variants) <= 15


def test_prematch_variants():
    hits = prematch_variants("DeepSeek 发布新模型", "", ["DeepSeek", "OpenAI"])
    assert hits == ["DeepSeek"]


# ---------- AIAnalysis 钳制 ----------
def test_analysis_clamp():
    a = AIAnalysis.model_validate({"relevance": 150, "importance": "low"})
    assert a.relevance == 100


# ---------- Provider：temperature 兼容性兜底（kimi k3 / o1 等锁定参数的模型） ----------


def _mk_provider(completions):
    """绕开 __init__（避免构造真实 SDK 客户端），直接注入假 client。"""
    provider = OpenAICompatProvider.__new__(OpenAICompatProvider)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider._model = "test-model"
    return provider


class _TempLockedCompletions:
    """模拟 k3-256k：显式传 temperature 直接 400"""

    def __init__(self):
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if "temperature" in kwargs:
            raise Exception("invalid temperature: only 1 is allowed for this model")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))]
        )


async def test_temperature_locked_model_fallback():
    fake = _TempLockedCompletions()
    provider = _mk_provider(fake)

    out = await provider._chat("测试", max_tokens=100, json_schema=None)

    assert out == '{"ok":true}'
    assert len(fake.calls) == 2  # 第一次带 temperature 被拒，第二次不带成功
    assert "temperature" in fake.calls[0]
    assert "temperature" not in fake.calls[1]


class _AlwaysFailCompletions:
    async def create(self, **kwargs):
        raise Exception("connection refused")


async def test_non_temperature_error_raises_aierror():
    provider = _mk_provider(_AlwaysFailCompletions())

    with pytest.raises(AIError):
        await provider._chat("测试", max_tokens=100, json_schema=None)
