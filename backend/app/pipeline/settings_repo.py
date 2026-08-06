"""运行时配置读取（FR-7.2）：Setting 表 KV，带默认值，修改后下一轮生效无需重启。"""

from sqlmodel import Session

from app.db import engine
from app.models import Setting

DEFAULTS: dict[str, str] = {
    "check_interval_minutes": "30",      # R-101 检查周期
    "twitter_quota": "15",               # R-202
    "other_quota": "10",                 # R-202
    "ai_concurrency": "3",               # AI 并发（沿用 1.0 经验值）
    "mail_importance_threshold": "high", # R-302 邮件阈值
}


def get_setting(key: str) -> str:
    with Session(engine) as session:
        row = session.get(Setting, key)
        if row is not None:
            return row.value
    return DEFAULTS.get(key, "")


def get_setting_int(key: str) -> int:
    try:
        return int(get_setting(key))
    except ValueError:
        return int(DEFAULTS.get(key, "0") or 0)


def set_setting(key: str, value: str) -> None:
    from datetime import UTC, datetime

    with Session(engine) as session:
        row = session.get(Setting, key) or Setting(key=key)
        row.value = value
        row.updated_at = datetime.now(UTC)
        session.add(row)
        session.commit()
