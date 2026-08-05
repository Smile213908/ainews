"""通知中心（FR-4）：已读/全部已读/删除/清空（R-304）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, func, select, update

from app.db import get_session
from app.models import Notification
from app.schemas import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    is_read: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[Notification]:
    stmt = select(Notification).order_by(col(Notification.created_at).desc()).limit(limit)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)
    return list(session.exec(stmt).all())


@router.get("/unread-count")
def unread_count(session: Session = Depends(get_session)) -> dict[str, int]:
    count = session.exec(
        select(func.count()).select_from(Notification).where(Notification.is_read == False)  # noqa: E712
    ).one()
    return {"unread": count}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: UUID, session: Session = Depends(get_session)) -> Notification:
    n = session.get(Notification, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    n.is_read = True
    session.add(n)
    session.commit()
    session.refresh(n)
    return n


@router.post("/read-all")
def mark_all_read(session: Session = Depends(get_session)) -> dict[str, int]:
    result = session.exec(
        update(Notification).where(Notification.is_read == False).values(is_read=True)  # noqa: E712
    )
    session.commit()
    return {"updated": result.rowcount or 0}


@router.post("/clear", status_code=204)
def clear_notifications(session: Session = Depends(get_session)) -> None:
    for n in session.exec(select(Notification)).all():
        session.delete(n)
    session.commit()


@router.delete("/{notification_id}", status_code=204)
def delete_notification(notification_id: UUID, session: Session = Depends(get_session)) -> None:
    n = session.get(Notification, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    session.delete(n)
    session.commit()
