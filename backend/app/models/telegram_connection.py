"""
One-time Telegram connection tokens.

Flow (multi-tenant, platform-managed bot):
1. User clicks "Connect Telegram" -> backend issues a secure random token.
   Only the SHA-256 hash of the token is persisted; the raw token is shown to
   the user once and embedded in a t.me deep link.
2. The user sends /start <token> to the platform bot.
3. The webhook maps telegram chat_id -> DevOps Monitor user_id and marks the
   token used. Tokens expire and are single-use, and never contain user data.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


def generate_connection_token() -> str:
    """Generate a secure, unpredictable, information-free connection token."""
    return secrets.token_urlsafe(24)


def hash_connection_token(token: str) -> str:
    """Hash a connection token for safe storage and constant-time lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TelegramConnectionToken(Document):
    """A short-lived, single-use token linking a Telegram chat to a user."""

    user_id: Indexed(str)
    token_hash: Indexed(str, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    used: bool = False
    used_at: Optional[datetime] = None
    # Filled in when the connection completes (safe identifiers only):
    chat_id: Optional[str] = None
    telegram_username: Optional[str] = None

    class Settings:
        name = "telegram_connection_tokens"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("used", 1)],
            [("expires_at", 1)],
        ]

    @staticmethod
    def build_expiry() -> datetime:
        from ..config import settings

        minutes = getattr(settings, "TELEGRAM_CONNECT_TOKEN_EXPIRE_MINUTES", 15)
        return datetime.utcnow() + timedelta(minutes=max(1, int(minutes)))

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    def is_valid(self) -> bool:
        return (not self.used) and (not self.is_expired())