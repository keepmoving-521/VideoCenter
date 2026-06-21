from datetime import datetime

from pydantic import BaseModel, ConfigDict

from videocenter.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_type: NotificationType
    download_task_id: int
    media_id: int | None
    title: str
    message: str
    read_at: datetime | None
    created_at: datetime


class NotificationUnreadCount(BaseModel):
    unread_count: int


class NotificationReadAllResult(BaseModel):
    updated_count: int
