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
        default_factory=lambda: ["alert", "recovery", "offline"]
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
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestNotificationRequest(BaseModel):
    provider: NotificationProviderType
    recipient: Optional[str] = None
    channel_id: Optional[str] = None


class ProviderStatus(BaseModel):
    enabled: bool
    configured: bool
    available: bool
    message: str


class ProviderStatusResponse(BaseModel):
    providers: Dict[str, ProviderStatus]


class EmailVerificationRequest(BaseModel):
    email: str


class EmailVerificationVerifyRequest(BaseModel):
    email: str
    code: str


class EmailVerificationResponse(BaseModel):
    success: bool
    # Failure results carry only "error" (no message); making message optional
    # lets real provider/validation failures return as 200 + success=false with
    # the sanitized error instead of a FastAPI ResponseValidationError (500).
    message: Optional[str] = None
    verified: Optional[bool] = None
    error: Optional[str] = None