"""AI 输出 schema（重构方案 §4.4）：structured output 的目标结构 + 降级钳制。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 三级过滤阈值（R-204），做成配置可 AB（ai/rules.py 读取）
DEFAULT_RELEVANCE_FLOOR = 50
DEFAULT_UNMENTIONED_FLOOR = 65


class AIAnalysis(BaseModel):
    is_real: bool = True
    relevance: int = Field(default=0, ge=0, le=100)
    relevance_reason: str = Field(default="", max_length=200)
    keyword_mentioned: bool = False
    importance: Literal["low", "medium", "high", "urgent"] = "low"
    summary: str = Field(default="", max_length=150)

    @field_validator("relevance", mode="before")
    @classmethod
    def _clamp_relevance(cls, v: object) -> int:
        try:
            return max(0, min(100, int(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0


class ExpandedQueries(BaseModel):
    variants: list[str] = Field(default_factory=list, max_length=15)


ANALYSIS_JSON_SCHEMA = {
    "name": "ai_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "is_real": {"type": "boolean"},
            "relevance": {"type": "integer"},
            "relevance_reason": {"type": "string"},
            "keyword_mentioned": {"type": "boolean"},
            "importance": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
            "summary": {"type": "string"},
        },
        "required": [
            "is_real",
            "relevance",
            "relevance_reason",
            "keyword_mentioned",
            "importance",
            "summary",
        ],
        "additionalProperties": False,
    },
}
