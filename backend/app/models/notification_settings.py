import enum
from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import Field


class NotificationProviderType(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class NotificationChannelConfig(Document):
    """User notification channel configuration."""
    
    user_id: Indexed(str)
    provider: NotificationProviderType
    enabled: bool = False
    recipient: str  # email, phone number, chat_id
    min_severity: str = "warning"  # info, warning, high, critical
    notification_types: List[str] = Field(
        default_factory=lambda: ["alert", "recovery", "offline", "security"]
    )
    cooldown_seconds: int = Field(default=300)  # 5 minutes default cooldown
    last_sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "notification_channels"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("provider", 1)],
            [("user_id", 1), ("enabled", 1)],
        ]