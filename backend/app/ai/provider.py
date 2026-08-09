"""AI Provider 抽象（技术选型 §7）：OpenAI 兼容实现 + 降级实现（R-207）。

接入方式：任意 OpenAI 兼容端点（官方 / DeepSeek / 通义 / OpenRouter / 自建 vLLM），
换 Provider 只改 AI_BASE_URL + AI_API_KEY + AI_MODEL 三个环境变量，零代码改动。
fallback 链：structured output → 正则提取 JSON → Pydantic 钳制 → 抛错进重试队列（R-205）。
"""

import json
import re
from typing import Protocol

import structlog
from openai import AsyncOpenAI

from app.ai.prompts import ANALYSIS_PROMPT, EXPAND_PROMPT
from app.ai.schemas import ANALYSIS_JSON_SCHEMA, AIAnalysis, ExpandedQueries
from app.config import get_settings

log = structlog.get_logger()

INPUT_MAX_CHARS = 2000  # R-203：输入截断
ANALYSIS_MAX_TOKENS = 500
EXPAND_MAX_TOKENS = 300
TEMPERATURE = 0.2  # R-203：保证一致性


class AIError(Exception):
    """AI 调用或解析彻底失败——调用方应进重试队列，不放行不丢弃（R-205）。"""


class AIProvider(Protocol):
    async def analyze(self, *, title: str, content: str, source: str, keyword: str,
                      prematch: list[str]) -> AIAnalysis: ...

    async def expand_query(self, keyword: str) -> list[str]: ...


def _extract_json(text: str) -> dict:
    """降级路径：从模型输出里正则捞第一个 JSON 对象。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise AIError("模型输出中未找到 JSON")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise AIError(f"JSON 解析失败: {e}") from e


class OpenAICompatProvider:
    """OpenAI SDK 指向任意兼容端点（ADR-6）：换 Provider 只改 base_url + key + model。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            timeout=60.0,
        )
        self._model = settings.ai_model

    async def _chat(self, prompt: str, *, max_tokens: int, json_schema: dict | None) -> str:
        kwargs: dict = {}
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=TEMPERATURE,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            raise AIError(f"AI 调用失败: {e}") from e
        return resp.choices[0].message.content or ""

    async def analyze(self, *, title: str, content: str, source: str, keyword: str,
                      prematch: list[str]) -> AIAnalysis:
        prompt = ANALYSIS_PROMPT.format(
            keyword=keyword,
            prematch=", ".join(prematch[:5]) or "无",
            title=title[:200],
            content=content[:INPUT_MAX_CHARS],
            source=source,
        )
        raw = await self._chat(prompt, max_tokens=ANALYSIS_MAX_TOKENS,
                               json_schema=ANALYSIS_JSON_SCHEMA)
        # structured output 直接解析；失败走正则降级 + Pydantic 钳制
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("ai_structured_output_fallback_regex", keyword=keyword)
            data = _extract_json(raw)
        try:
            return AIAnalysis.model_validate(data)
        except Exception as e:
            raise AIError(f"AI 输出校验失败: {e}") from e

    async def expand_query(self, keyword: str) -> list[str]:
        prompt = EXPAND_PROMPT.format(keyword=keyword)
        raw = await self._chat(prompt, max_tokens=EXPAND_MAX_TOKENS, json_schema=None)
        data = _extract_json(raw)
        try:
            parsed = ExpandedQueries.model_validate(data)
        except Exception as e:
            raise AIError(f"查询扩展输出校验失败: {e}") from e
        variants = [v.strip() for v in parsed.variants if v.strip()]
        return variants[:15] or [keyword]


class DegradedProvider:
    """R-207：AI 未配置时全流程仍可运行，产出降级默认值并由调用方标记"未经 AI 审核"。"""

    async def analyze(self, *, title: str, content: str, source: str, keyword: str,
                      prematch: list[str]) -> AIAnalysis:
        mentioned = keyword.lower() in f"{title} {content}".lower()
        return AIAnalysis(
            is_real=True,
            relevance=60 if mentioned else 40,
            relevance_reason="未经 AI 审核（AI 服务未配置）",
            keyword_mentioned=mentioned,
            importance="low",
            summary="未经 AI 审核",
        )

    async def expand_query(self, keyword: str) -> list[str]:
        return rule_based_expand(keyword)


def rule_based_expand(keyword: str) -> list[str]:
    """规则法查询扩展（R-201 降级）：拆分 + 两两组合。"""
    words = [w for w in re.split(r"[\s\-_/]+", keyword) if w]
    variants = {keyword}
    for w in words:
        variants.add(w)
    for i in range(len(words)):
        for j in range(i + 1, len(words)):
            variants.add(f"{words[i]} {words[j]}")
            variants.add(f"{words[i]}-{words[j]}")
    return list(variants)[:15]


def get_provider() -> AIProvider:
    settings = get_settings()
    if settings.ai_api_key:
        return OpenAICompatProvider()
    log.warning("ai_not_configured_degraded_mode")
    return DegradedProvider()
