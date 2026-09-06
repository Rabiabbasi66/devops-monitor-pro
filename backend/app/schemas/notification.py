from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..models.notification import NotificationType


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    alert_id: Optional[str] = None
    type: NotificationType
    title: str
    message: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread: int
