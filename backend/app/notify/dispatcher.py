"""通知分发（R-301/R-302）：通知中心落库 + WS 实时推送 + 邮件分级。"""

import structlog
from sqlmodel import Session

from app.db import engine
from app.models import Hotspot, Notification
from app.notify.emailer import send_hotspot_email
from app.notify.ws import ws_manager
from app.pipeline.settings_repo import get_setting

log = structlog.get_logger()

_IMPORTANCE_ORDER = {"low": 0, "medium": 1, "high": 2, "urgent": 3}


def _should_email(importance: str) -> bool:
    threshold = get_setting("mail_importance_threshold") or "high"
    return _IMPORTANCE_ORDER.get(importance, 0) >= _IMPORTANCE_ORDER.get(threshold, 2)


async def dispatch_hotspot(hotspot: Hotspot, keyword: str) -> None:
    # ① 通知中心落库
    with Session(engine) as session:
        session.add(
            Notification(
                type="hotspot",
                title=f"新热点：{hotspot.title[:80]}",
                content=hotspot.summary or "",
                hotspot_id=hotspot.id,
            )
        )
        session.commit()

    # ② WS：关键词房间定向 + 全局广播（R-301）
    await ws_manager.broadcast(
        "hotspot:new",
        {
            "id": str(hotspot.id),
            "title": hotspot.title,
            "source": hotspot.source,
            "importance": hotspot.importance,
            "summary": hotspot.summary,
            "keyword": keyword,
            "hot_score": hotspot.hot_score,
            "created_at": hotspot.created_at,
        },
        keyword=keyword,
    )

    # ③ 邮件：仅 high/urgent（R-302，阈值可配置）
    if _should_email(hotspot.importance):
        await send_hotspot_email(hotspot, keyword)
