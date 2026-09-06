from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from ..models.notification_settings import NotificationProviderType


class NotificationChannelCreate(BaseModel):
    provider: NotificationProviderType
    enabled: bool = False
    recipient: str
    min_severity: str = "warning"
    notification_types: List[str] = Field(
        default_factory=lambda: ["alert", "recovery", "offline", "security"]
    )
    cooldown_seconds: int = 300


class NotificationChannelUpdate(BaseModel):
    enabled: Optional[bool] = None
    recipient: Optional[str] = None
    min_severity: Optional[str] = None
    notification_types: Optional[List[str]] = None
    cooldown_seconds: Optional[int] = None


class NotificationChannelResponse(BaseModel):
    id: str
    user_id: str
    provider: NotificationProviderType
    enabled: bool
    recipient: str
    min_severity: str
    notification_types: List[str]
    cooldown_seconds: int
    last_sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestNotificationRequest(BaseModel):
    provider: NotificationProviderType
    recipient: str