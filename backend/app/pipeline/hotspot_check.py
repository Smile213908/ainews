"""热点检查流水线（重构方案 §4.1）：8 个显式阶段，每阶段可单测。

① 互斥锁 → ② 账号检测(B站) → ③ 查询扩展 → ④ 6源并行采集 → ⑤ 清洗
→ ⑥ 库内批量查重 → ⑦ 配额前置 → ⑧ AI 批量分析 → 阈值过滤 → 落库 → 分级通知
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field

import structlog
from sqlmodel import Session, select

from app.ai.analysis import AIAnalyzer
from app.ai.expand import expand_query, prematch_variants
from app.ai.provider import AIProvider, DegradedProvider
from app.ai.rules import passes_threshold
from app.collectors import registry
from app.collectors.base import CollectorError, SearchResult, SourceUnavailable
from app.core import source_health
from app.core.redis import acquire_lock, release_lock, renew_lock
from app.db import engine
from app.models import Hotspot, Keyword
from app.notify.dispatcher import dispatch_hotspot
from app.pipeline.cleaning import clean
from app.pipeline.quota import apply_quota
from app.pipeline.settings_repo import get_setting_int
from app.scoring import calc_hot_score, importance_rank

log = structlog.get_logger()

LOCK_NAME = "hotspot_check"
LOCK_TTL = 1800  # 30 分钟，大于单轮上限


@dataclass
class CheckProgress:
    """手动触发 409 时返回的进度信息（R-102）。"""

    running: bool = False
    run_id: str | None = None
    total_keywords: int = 0
    done_keywords: int = 0
    current_keyword: str | None = None
    hotspots_created: int = 0
    ai_calls: int = 0
    started_at: float = 0.0


progress = CheckProgress()


@dataclass
class KeywordReport:
    keyword: str
    collected: int = 0
    candidates: int = 0
    analyzed: int = 0
    created: int = 0
    errors: list[str] = field(default_factory=list)


async def _collect_all(keyword: str) -> list[SearchResult]:
    """Stage 3-4：6 源并行采集，单源失败隔离 + 计入源健康（R-103）。"""
    collectors = registry.enabled()

    async def run_one(c) -> list[SearchResult]:
        try:
            results = await c.search(keyword)
            source_health.record_success(c.name)
            return results
        except SourceUnavailable as e:
            log.info("source_skipped", source=c.name, reason=str(e))
            return []
        except CollectorError as e:
            source_health.record_failure(c.name, str(e))
            log.warning("source_failed", source=c.name, error=str(e))
            return []
        except Exception as e:
            source_health.record_failure(c.name, f"未分类错误: {e}")
            log.exception("source_crashed", source=c.name)
            return []

    batches = await asyncio.gather(*(run_one(c) for c in collectors))
    return [item for batch in batches for item in batch]


def _filter_existing(items: list[SearchResult]) -> list[SearchResult]:
    """Stage 5：库内批量查重（修复 1.0 逐条 SELECT 的 N+1）。"""
    if not items:
        return []
    with Session(engine) as session:
        pairs = {(i.url, i.source) for i in items}
        urls = [u for u, _ in pairs]
        existing = session.exec(
            select(Hotspot.url, Hotspot.source).where(Hotspot.url.in_(urls))  # type: ignore[attr-defined]
        ).all()
    existing_pairs = {(u, s) for u, s in existing}
    return [i for i in items if (i.url, i.source) not in existing_pairs]


def _to_hotspot(item: SearchResult, analysis, keyword: Keyword, ai_reviewed: bool) -> Hotspot:
    hs = Hotspot(
        title=item.title[:500],
        content=item.content,
        url=item.url[:1000],
        source=item.source,
        source_id=item.source_id,
        is_real=analysis.is_real,
        relevance=analysis.relevance,
        relevance_reason=analysis.relevance_reason,
        keyword_mentioned=analysis.keyword_mentioned,
        importance=analysis.importance,
        summary=analysis.summary,
        ai_reviewed=ai_reviewed,
        view_count=item.view_count,
        like_count=item.like_count,
        retweet_count=item.retweet_count,
        reply_count=item.reply_count,
        comment_count=item.comment_count,
        quote_count=item.quote_count,
        danmaku_count=item.danmaku_count,
        author_name=item.author_name,
        author_avatar=item.author_avatar,
        author_verified=item.author_verified,
        published_at=item.published_at,
        keyword_id=keyword.id,
        raw_payload=item.raw_payload,
    )
    # 落库时预计算（R-401/R-402）
    hs.hot_score = calc_hot_score(hs.like_count, hs.retweet_count, hs.view_count)
    hs.importance_rank = importance_rank(hs.importance)
    return hs


async def process_keyword(kw: Keyword, provider: AIProvider, analyzer: AIAnalyzer) -> KeywordReport:
    report = KeywordReport(keyword=kw.text)
    progress.current_keyword = kw.text

    # Stage 2：查询扩展（缓存 7 天，AI 不可用走规则法）
    variants = await expand_query(kw.text, provider)
    # 用全部变体做第一轮采集（主查询词），变体用于预匹配
    raw = await _collect_all(kw.text)
    report.collected = len(raw)

    # Stage 4：清洗（去重 → 新鲜度 → 优先级）
    cleaned = clean(raw)
    # Stage 5：库内批量查重
    candidates = _filter_existing(cleaned)
    report.candidates = len(candidates)
    # Stage 6：配额前置（R-202）——AI 调用量硬上限
    budgeted = apply_quota(
        candidates,
        twitter_quota=get_setting_int("twitter_quota"),
        other_quota=get_setting_int("other_quota"),
    )
    # Stage 7：AI 批量分析（文本预匹配命中变体作为上下文）
    ai_reviewed = not isinstance(provider, DegradedProvider)
    analyzed = await analyzer.analyze_batch(
        budgeted, kw.text, prematch_variants(" ".join(i.title for i in budgeted), "", variants)
    )
    report.analyzed = len(analyzed)

    # Stage 8：阈值过滤 → 落库 → 分级通知
    with Session(engine) as session:
        for ai_item in analyzed:
            if not passes_threshold(ai_item.analysis):
                continue
            hs = _to_hotspot(ai_item.item, ai_item.analysis, kw, ai_reviewed)
            session.add(hs)
            session.commit()
            session.refresh(hs)
            report.created += 1
            progress.hotspots_created += 1
            await dispatch_hotspot(hs, kw.text)
    return report


async def _watchdog(token: str, stop: asyncio.Event) -> None:
    """锁看门狗：每 10 分钟续期，防长任务锁过期（技术选型 §5.1）。"""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=600)
        except TimeoutError:
            await renew_lock(LOCK_NAME, LOCK_TTL, token)


async def run_hotspot_check(trigger: str = "cron") -> dict:
    """整轮检查入口：先抢锁，抢不到返回冲突信息（R-102）。"""
    run_id = str(uuid.uuid4())
    token = f"{run_id}:{trigger}"
    if not await acquire_lock(LOCK_NAME, LOCK_TTL, token):
        return {"ok": False, "conflict": True, "progress": progress.__dict__}

    progress.running = True
    progress.run_id = run_id
    progress.done_keywords = 0
    progress.hotspots_created = 0
    progress.ai_calls = 0
    progress.started_at = time.monotonic()

    stop_watchdog = asyncio.Event()
    watchdog_task = asyncio.create_task(_watchdog(token, stop_watchdog))

    provider = _get_provider()
    analyzer = AIAnalyzer(provider, concurrency=get_setting_int("ai_concurrency"))
    reports: list[dict] = []
    started = time.time()
    try:
        with Session(engine) as session:
            keywords = list(
                session.exec(select(Keyword).where(Keyword.is_active == True)).all()  # noqa: E712
            )
        progress.total_keywords = len(keywords)
        log.info("check_started", run_id=run_id, trigger=trigger, keywords=len(keywords))

        for kw in keywords:
            try:
                report = await process_keyword(kw, provider, analyzer)
            except Exception as e:
                log.exception("keyword_failed", run_id=run_id, keyword=kw.text)
                report = KeywordReport(keyword=kw.text, errors=[str(e)])
            reports.append(report.__dict__)
            progress.done_keywords += 1
            progress.ai_calls = analyzer.stats["calls"]
            await asyncio.sleep(2)  # 关键词间串行，控制外网请求速率
    finally:
        stop_watchdog.set()
        watchdog_task.cancel()
        await release_lock(LOCK_NAME, token)
        progress.running = False
        progress.current_keyword = None

    result = {
        "ok": True,
        "run_id": run_id,
        "duration_seconds": round(time.time() - started, 1),
        "keywords": len(reports),
        "ai_calls": analyzer.stats["calls"],
        "ai_cache_hits": analyzer.stats["cache_hits"],
        "hotspots_created": progress.hotspots_created,
        "reports": reports,
    }
    log.info(
        "check_run_completed",
        run_id=run_id,
        keywords=len(reports),
        ai_calls=analyzer.stats["calls"],
        hotspots=progress.hotspots_created,
        duration=result["duration_seconds"],
    )
    return result


def _get_provider() -> AIProvider:
    from app.ai.provider import get_provider

    return get_provider()
