"""手动触发检查（FR-7.3 / R-102）。

- POST /check-hotspots：全量检查；POST /keywords/{id}/check：单关键词立即检查；
- 锁空闲：后台启动，立即返回受理；锁占用：409 + 当前进度。
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Setting
from app.pipeline.hotspot_check import progress, run_hotspot_check, run_single_keyword_check
from app.pipeline.settings_repo import DEFAULTS, set_setting

router = APIRouter(tags=["control"])

_background: set[asyncio.Task] = set()


def _conflict_409() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "message": "检查进行中",
            "progress": {
                "total_keywords": progress.total_keywords,
                "done_keywords": progress.done_keywords,
                "current_keyword": progress.current_keyword,
                "hotspots_created": progress.hotspots_created,
                "run_id": progress.run_id,
            },
        },
    )


def _launch(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)

    def _log_result(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            import structlog

            structlog.get_logger().exception("manual_check_failed", error=str(exc))

    task.add_done_callback(_log_result)


@router.post("/check-hotspots", status_code=202)
async def trigger_check() -> dict:
    if progress.running:
        raise _conflict_409()
    _launch(run_hotspot_check(trigger="manual"))
    await asyncio.sleep(0)
    return {"ok": True, "message": "检查已启动", "run_id": progress.run_id}


@router.post("/keywords/{keyword_id}/check", status_code=202)
async def trigger_keyword_check(
    keyword_id: UUID, session: Session = Depends(get_session)
) -> dict:
    """单关键词立即检查：与全量检查共用锁，冲突返回 409 + 进度；关键词不存在返回 404。"""
    from app.models import Keyword

    if session.get(Keyword, keyword_id) is None:
        raise HTTPException(status_code=404, detail="关键词不存在")
    if progress.running:
        raise _conflict_409()
    _launch(run_single_keyword_check(keyword_id, trigger="manual"))
    await asyncio.sleep(0)
    return {"ok": True, "message": "检查已启动", "run_id": progress.run_id}


@router.get("/check-hotspots/status")
def check_status() -> dict:
    return {
        "running": progress.running,
        "run_id": progress.run_id,
        "total_keywords": progress.total_keywords,
        "done_keywords": progress.done_keywords,
        "current_keyword": progress.current_keyword,
        "hotspots_created": progress.hotspots_created,
        "ai_calls": progress.ai_calls,
    }


@router.get("/settings")
def list_settings(session: Session = Depends(get_session)) -> dict[str, str]:
    rows = session.exec(select(Setting)).all()
    stored = {r.key: r.value for r in rows}
    return {**DEFAULTS, **stored}


@router.put("/settings/{key}")
def update_setting(key: str, body: dict) -> dict:
    if key not in DEFAULTS:
        raise HTTPException(status_code=404, detail=f"未知配置项: {key}")
    value = str(body.get("value", "")).strip()
    if not value:
        raise HTTPException(status_code=422, detail="配置值不能为空")
    set_setting(key, value)  # 下一轮检查生效，无需重启（FR-7.2）
    return {"key": key, "value": value}
