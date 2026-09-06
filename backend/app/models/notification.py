import enum
from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


class NotificationType(str, enum.Enum):
    ALERT = "alert"
    SYSTEM = "system"
    RECOVERY = "recovery"


class Notification(Document):
    user_id: Indexed(str)
    alert_id: Optional[str] = None
    type: NotificationType
    title: str
    message: str
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "notifications"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("read", 1)],
            [("created_at", -1)],
        ]
