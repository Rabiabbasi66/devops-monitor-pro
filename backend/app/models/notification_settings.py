import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from beanie import Document, Indexed
from pydantic import Field


class NotificationProviderType(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


# Key fragments that must never be persisted in provider_metadata.
# Platform provider credentials live only in config.py / environment.
_SECRET_METADATA_KEY_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "credential",
    "access",
)


def sanitize_provider_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Strip any secret-looking keys from provider metadata.

    Only safe identifiers (chat_id, telegram_username, phone_number, ...) are
    allowed to be stored on a user's channel document. Defense in depth:
    secrets belong to the platform, never to a user document.
    """
    if not metadata:
        return {}
    safe: Dict[str, Any] = {}
    for key, value in metadata.items():
        key_lower = str(key).lower()
        if any(fragment in key_lower for fragment in _SECRET_METADATA_KEY_FRAGMENTS):
            continue
        safe[key] = value
    return safe


class NotificationChannelConfig(Document):
    """User notification channel configuration.

    Multi-tenancy: every document belongs to exactly one user (``user_id``)
    and every service/router access must be scoped to the owning user.

    Security: platform provider credentials (SMTP password, WhatsApp access
    token, Telegram bot token) are NEVER stored here. Only safe identifiers
    live in ``provider_metadata`` (e.g. chat_id, telegram_username).
    """

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
    # Safe, provider-specific metadata only (see sanitize_provider_metadata)
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "notification_channels"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("provider", 1)],
            [("user_id", 1), ("enabled", 1)],
        ]