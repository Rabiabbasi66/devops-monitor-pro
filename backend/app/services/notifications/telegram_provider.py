"""
Telegram notification provider using Telegram Bot API.

Platform-managed: a single platform bot token comes from environment
configuration. Users connect their own chat via a one-time connection token.
The bot token is never logged, never returned by the API, and never stored on
user documents.
"""
import logging
import re
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from .base import NotificationProvider, NotificationSendResult
from ...utils.secret_masking import redact_secrets, safe_error_detail

logger = logging.getLogger("devops_monitor")


class TelegramProvider(NotificationProvider):
    """Telegram notification provider using Telegram Bot API."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get("telegram_bot_token", "")
        self.api_timeout = config.get("telegram_timeout", 30)
        self.parse_mode = config.get("telegram_parse_mode", "HTML")

    def missing_config(self) -> Optional[str]:
        """Platform Telegram configuration completeness check (no secrets).

        Evaluates configuration regardless of the enabled flag so the
        provider-status endpoint can report configured=false honestly.
        """
        if not self.bot_token:
            return "Telegram provider is not configured (missing bot token)"
        return None

    def validate_recipient(self, recipient: str) -> Optional[str]:
        base_error = super().validate_recipient(recipient)
        if base_error:
            return base_error
        value = str(recipient).strip()
        if value.startswith("@"):
            if len(value) < 2:
                return "Invalid Telegram channel name"
            return None
        # chat ids are numeric (possibly negative for groups/channels)
        if not re.fullmatch(r"-?\d{4,}", value):
            return "Invalid Telegram chat id"
        return None

    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send Telegram message."""
        if not self.enabled:
            logger.debug("Telegram provider is disabled")
            return False

        result = await self.send_with_result(recipient, title, message, severity, metadata)
        return result.success

    async def send_with_result(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NotificationSendResult:
        """Send a Telegram message and return a detailed (secret-free) result."""
        if not self.enabled:
            logger.debug("Telegram provider is disabled")
            return NotificationSendResult(False, "Telegram provider is not enabled")

        missing = self.missing_config()
        if missing:
            logger.error(
                "Telegram provider missing configuration (bot token configured: %s)",
                bool(self.bot_token),
            )
            return NotificationSendResult(False, missing)

        recipient_error = self.validate_recipient(recipient)
        if recipient_error:
            return NotificationSendResult(False, recipient_error)

        try:
            # Create message payload
            payload = {
                "chat_id": recipient,
                "text": self._format_message(title, message, severity, metadata),
                "parse_mode": self.parse_mode
            }

            # Send to Telegram Bot API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        logger.info("Telegram message sent successfully to chat_id %s", recipient)
                        return NotificationSendResult(True)
                    return self._map_api_error(400, str(result.get("description", "")))

                return self._map_api_error(response.status_code, response.text)

        except httpx.TimeoutException:
            logger.error("Telegram request timed out after %ss", self.api_timeout)
            return NotificationSendResult(False, "Telegram request timed out")
        except Exception as exc:
            # Redact the bot token (it is part of the request URL) before logging
            logger.error(
                "Failed to send Telegram message: %s",
                redact_secrets(str(exc), [self.bot_token]),
            )
            return NotificationSendResult(False, "Failed to reach Telegram API")

    def _map_api_error(self, status_code: int, body: str) -> NotificationSendResult:
        """Map a Telegram Bot API failure to a safe, useful error message."""
        detail = safe_error_detail(body, [self.bot_token])
        detail_lower = (detail or "").lower()

        if "bot was blocked" in detail_lower:
            error = "Telegram bot is blocked by the recipient"
        elif "chat not found" in detail_lower:
            error = "Invalid Telegram chat id (chat not found)"
        elif status_code in (401, 404) or "unauthorized" in detail_lower:
            error = "Telegram bot token is invalid or revoked"
        elif status_code == 429 or "too many requests" in detail_lower:
            error = "Telegram rate limit exceeded, try again later"
        else:
            error = "Telegram API error"

        # Log the failure factually - never the bot token itself
        logger.error(
            "Telegram API error: status=%s detail=%s (bot token configured: %s)",
            status_code,
            detail,
            bool(self.bot_token),
        )
        return NotificationSendResult(False, error)
    
    async def send_test(self, recipient: str) -> bool:
        """Send test Telegram message."""
        return await self.send(
            recipient=recipient,
            title="Test Notification",
            message="This is a test notification from DevOps Monitor Pro. Your Telegram configuration is working correctly.",
            severity="info",
            metadata={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
    
    def _format_message(
        self,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """Format message for Telegram."""
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "high": "🔶",
            "critical": "🔴"
        }
        emoji = severity_emoji.get(severity.lower(), "⚡")
        
        # Use HTML formatting
        formatted = f"<b>{emoji} {severity.upper()}</b>\n\n<b>{title}</b>\n\n{message}"
        
        if metadata:
            formatted += "\n\n<b>📋 Details:</b>"
            for key, value in metadata.items():
                if key != "test":
                    formatted += f"\n• <code>{key}:</code> {value}"
            formatted += f"\n\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return formatted