"""搜索异步任务（FR-3.2）：提交即返回 task_id（≤1s），任务状态机 + 超时。

状态：queued → running → completed / failed（超时默认 120s）。
结果通过 GET /api/search/{task_id} 轮询获取，同时 WS 广播 task:update。
单实例进程内存储；多实例时迁移 Redis（key 前缀 task:search:*）。
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()

TASK_TIMEOUT = 120.0  # 秒（FR-3.2）


@dataclass
class SearchTask:
    id: str
    query: str
    status: str = "queued"  # queued/running/completed/failed
    created_at: float = field(default_factory=time.time)
    result: list[dict[str, Any]] | None = None
    error: str | None = None


_tasks: dict[str, SearchTask] = {}
_background_tasks: set[asyncio.Task] = set()


def get_task(task_id: str) -> SearchTask | None:
    return _tasks.get(task_id)


async def _run(task: SearchTask, executor) -> None:
    task.status = "running"
    try:
        result = await asyncio.wait_for(executor(task.query), timeout=TASK_TIMEOUT)
        task.result = result
        task.status = "completed"
    except TimeoutError:
        task.status = "failed"
        task.error = f"搜索超时（>{int(TASK_TIMEOUT)}s）"
        log.warning("search_task_timeout", task_id=task.id, query=task.query)
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        log.exception("search_task_failed", task_id=task.id)
    finally:
        # WS 推送任务终态（FR-3.2）
        from app.notify.ws import ws_manager

        await ws_manager.broadcast(
            "task:update",
            {
                "task_id": task.id,
                "status": task.status,
                "result_count": len(task.result) if task.result else 0,
                "error": task.error,
            },
        )
        log.info(
            "search_task_completed" if task.status == "completed" else "search_task_failed",
            task_id=task.id,
            duration=round(time.time() - task.created_at, 1),
            results=len(task.result) if task.result else 0,
        )


def submit(query: str, executor) -> SearchTask:
    """executor: async (query) -> list[dict]。提交后立即返回，后台执行。"""
    task = SearchTask(id=str(uuid.uuid4()), query=query)
    _tasks[task.id] = task
    runner = asyncio.create_task(_run(task, executor))
    _background_tasks.add(runner)
    runner.add_done_callback(_background_tasks.discard)
    # 简单清理：保留最近 200 个任务
    if len(_tasks) > 200:
        for old_id in sorted(_tasks, key=lambda i: _tasks[i].created_at)[:-200]:
            _tasks.pop(old_id, None)
    return task
