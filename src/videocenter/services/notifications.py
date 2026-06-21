from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.download import DownloadTask
from videocenter.models.media import Media
from videocenter.models.notification import Notification, NotificationType


def create_download_completed_notification(
    db: Session,
    *,
    task: DownloadTask,
) -> Notification:
    existing = db.scalar(select(Notification).where(Notification.download_task_id == task.id))
    if existing is not None:
        return existing
    media = db.get(Media, task.media_id) if task.media_id is not None else None
    display_name = media.title if media is not None else task.target_name
    notification = Notification(
        notification_type=NotificationType.DOWNLOAD_COMPLETED,
        download_task_id=task.id,
        media_id=task.media_id,
        title="下载完成",
        message=f"《{display_name}》已下载完成",
    )
    db.add(notification)
    return notification


def mark_notification_read(notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = datetime.now()
    return notification
