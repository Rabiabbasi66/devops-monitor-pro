"""
Secret masking helpers.

These helpers guarantee that platform provider credentials (SMTP password,
WhatsApp access token, Telegram bot token) never appear in logs, exception
messages, or API responses. Providers only log facts like
"WhatsApp credentials configured: true" instead of secret values.
"""
import logging
from typing import Iterable, Optional

logger = logging.getLogger("devops_monitor")

_REDACTED = "[redacted]"


def mask_secret(value: Optional[str]) -> str:
    """Return a masked representation of a secret (never the secret itself)."""
    return "***" if value else ""


def redact_secrets(text: Optional[str], secrets: Iterable[Optional[str]]) -> str:
    """Remove any occurrence of the given secret values from ``text``.

    Secrets shorter than 4 characters are ignored to avoid mangling messages,
    but real provider credentials are always far longer than that.
    """
    if not text:
        return ""
    sanitized = text
    for secret in secrets:
        if secret and len(secret) >= 4 and secret in sanitized:
            sanitized = sanitized.replace(secret, _REDACTED)
    return sanitized


def safe_error_detail(text: Optional[str], secrets: Iterable[Optional[str]], limit: int = 300) -> str:
    """Truncate and redact an upstream API response body before logging."""
    return redact_secrets((text or "")[:limit], secrets)