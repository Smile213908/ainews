"""数据源健康记录与告警（FR-6 / R-303）。

- 每次采集结束记录成功/失败；
- 连续失败 ≥3 轮产生 alert 通知；同一源恢复前不重复告警（FR-6.2）；
- 成功后清零并自动"恢复"告警状态。
"""

from datetime import UTC, datetime

import structlog
from sqlmodel import Session

from app.db import engine
from app.models import Notification, SourceHealth

log = structlog.get_logger()

ALERT_THRESHOLD = 3


def record_success(source: str) -> None:
    with Session(engine) as session:
        health = session.get(SourceHealth, source) or SourceHealth(source=source)
        health.last_success_at = datetime.now(UTC)
        health.last_error = None
        health.consecutive_failures = 0
        health.alert_open = False
        session.add(health)
        session.commit()


def record_failure(source: str, error: str) -> bool:
    """记录失败；若本轮触发告警（达到阈值且之前未告警）返回 True。"""
    with Session(engine) as session:
        health = session.get(SourceHealth, source) or SourceHealth(source=source)
        health.last_failure_at = datetime.now(UTC)
        health.last_error = error[:500]
        health.consecutive_failures += 1
        triggered = False
        if health.consecutive_failures >= ALERT_THRESHOLD and not health.alert_open:
            health.alert_open = True
            triggered = True
            session.add(
                Notification(
                    type="alert",
                    title=f"数据源「{source}」连续失败 {health.consecutive_failures} 轮",
                    content=f"最近错误：{health.last_error}",
                )
            )
            log.warning("source_alert", source=source, failures=health.consecutive_failures)
        session.add(health)
        session.commit()
        return triggered
