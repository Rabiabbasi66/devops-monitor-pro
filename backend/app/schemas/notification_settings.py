from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
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
    # Safe identifiers only (chat_id, telegram_username, ...). Secrets are
    # never stored on channel documents, so this can be returned safely.
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestNotificationRequest(BaseModel):
    provider: NotificationProviderType
    # Optional: falls back to the user's saved channel for this provider
    recipient: Optional[str] = None
    channel_id: Optional[str] = None


class ProviderStatus(BaseModel):
    """Platform-level provider availability (no secrets)."""

    enabled: bool
    configured: bool
    available: bool
    message: str


class ProviderStatusResponse(BaseModel):
    providers: Dict[str, ProviderStatus]


class TelegramConnectResponse(BaseModel):
    success: bool
    token: str
    bot_username: Optional[str] = None
    connect_url: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class TelegramConnectStatusResponse(BaseModel):
    connected: bool
    pending: Optional[bool] = None
    expired: Optional[bool] = None
    chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class TelegramDisconnectResponse(BaseModel):
    success: bool
    disconnected: bool
    channels_removed: int