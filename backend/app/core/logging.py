"""structlog 结构化日志（技术选型 §8.2 / PRD §6 可观测）。

- 输出带时间戳/级别/事件名的结构化日志；
- 流水线各阶段注入 run_id / keyword / source 上下文，单轮检查可按 run_id 追溯；
- 生产设 LOG_JSON=1 切 JSON 输出（便于采集）。
"""

import logging
import os

import structlog

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    as_json = os.environ.get("LOG_JSON") == "1"
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[
            *processors,
            structlog.processors.JSONRenderer(ensure_ascii=False)
            if as_json
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
