from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import NotFoundError
from videocenter.models.notification import Notification
from videocenter.schemas.notification import (
    NotificationRead,
    NotificationReadAllResult,
    NotificationUnreadCount,
)
from videocenter.services.notifications import mark_notification_read

router = APIRouter()


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(Notification)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    return db.scalars(
        statement.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    ).all()


@router.get("/unread-count", response_model=NotificationUnreadCount)
def unread_notification_count(db: Session = Depends(get_db)):
    count = (
        db.scalar(select(func.count(Notification.id)).where(Notification.read_at.is_(None))) or 0
    )
    return NotificationUnreadCount(unread_count=count)


@router.post("/read-all", response_model=NotificationReadAllResult)
def read_all_notifications(db: Session = Depends(get_db)):
    result = db.execute(
        update(Notification).where(Notification.read_at.is_(None)).values(read_at=datetime.now())
    )
    db.commit()
    return NotificationReadAllResult(updated_count=result.rowcount or 0)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def read_notification(
    notification_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise NotFoundError("通知不存在", code="NOTIFICATION_NOT_FOUND")
    mark_notification_read(notification)
    db.commit()
    db.refresh(notification)
    return notification
