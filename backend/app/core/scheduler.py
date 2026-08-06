"""任务调度（技术选型 §5.1）：APScheduler 4 AsyncScheduler，与 FastAPI 同进程。

- 每 30 分钟触发一轮（R-101，周期可在 Setting 表调整）；
- 触发即抢 Redis 分布式锁，手动/定时共用同一把锁（R-102）；
- 升级路径：规模扩大后把触发器与执行器拆开（arq/Dramatiq），接口不变。

注意：APScheduler 4 要求调度器作为 async context manager 使用，
因此由 FastAPI lifespan 通过 AsyncExitStack 持有其生命周期。
"""

from contextlib import AsyncExitStack

import structlog
from apscheduler import AsyncScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.pipeline.hotspot_check import run_hotspot_check
from app.pipeline.settings_repo import get_setting_int

log = structlog.get_logger()


async def start_scheduler(stack: AsyncExitStack) -> None:
    minutes = max(1, get_setting_int("check_interval_minutes") or 30)
    scheduler = AsyncScheduler()
    await stack.enter_async_context(scheduler)
    await scheduler.add_schedule(
        run_hotspot_check,
        IntervalTrigger(minutes=minutes),
        id="hotspot_check",
        kwargs={"trigger": "cron"},
    )
    await scheduler.start_in_background()
    log.info("scheduler_started", interval_minutes=minutes)
