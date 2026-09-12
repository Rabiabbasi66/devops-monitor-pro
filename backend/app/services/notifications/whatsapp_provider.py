"""
WhatsApp notification provider using Meta WhatsApp Cloud API.

Platform-managed: the WhatsApp sender (phone number ID + access token) is
platform infrastructure configured via environment variables. Users only
connect their destination phone number. The access token is never logged,
never returned by the API, and never stored on user documents.
"""
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from .base import NotificationProvider, NotificationSendResult
from ...utils.secret_masking import redact_secrets, safe_error_detail
from ...utils.validators import normalize_phone_e164

logger = logging.getLogger("devops_monitor")


class WhatsAppProvider(NotificationProvider):
    """WhatsApp notification provider using WhatsApp Business API."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("whatsapp_api_url", "https://graph.facebook.com/v17.0")
        self.phone_number_id = config.get("whatsapp_phone_number_id", "")
        self.access_token = config.get("whatsapp_access_token", "")
        self.api_timeout = config.get("whatsapp_timeout", 30)

    def missing_config(self) -> Optional[str]:
        """Platform WhatsApp configuration completeness check (no secrets).

        Evaluates configuration regardless of the enabled flag so the
        provider-status endpoint can report configured=false honestly.
        """
        if not self.phone_number_id and not self.access_token:
            return "WhatsApp provider is not configured"
        if not self.phone_number_id:
            return "WhatsApp provider is not configured (missing phone number ID)"
        if not self.access_token:
            return "WhatsApp provider is not configured (missing access token)"
        return None

    def validate_recipient(self, recipient: str) -> Optional[str]:
        base_error = super().validate_recipient(recipient)
        if base_error:
            return base_error
        if normalize_phone_e164(str(recipient)) is None:
            return (
                "Invalid WhatsApp recipient: use an international phone number "
                "in E.164 format (e.g. +923001234567)"
            )
        return None

    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send WhatsApp message."""
        if not self.enabled:
            logger.debug("WhatsApp provider is disabled")
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
        """Send a WhatsApp message and return a detailed (secret-free) result."""
        if not self.enabled:
            logger.debug("WhatsApp provider is disabled")
            return NotificationSendResult(False, "WhatsApp provider is not enabled")

        missing = self.missing_config()
        if missing:
            logger.error(
                "WhatsApp provider missing configuration (credentials configured: %s)",
                bool(self.phone_number_id and self.access_token),
            )
            return NotificationSendResult(False, missing)

        recipient_error = self.validate_recipient(recipient)
        if recipient_error:
            return NotificationSendResult(False, recipient_error)

        try:
            # Meta Cloud API expects the number without the leading "+"
            phone_number = normalize_phone_e164(str(recipient)).lstrip("+")

            # Create message payload
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {
                    "body": self._format_message(title, message, severity, metadata)
                }
            }

            # Send to WhatsApp Cloud API
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    logger.info("WhatsApp message sent successfully to %s", phone_number)
                    return NotificationSendResult(True)
                return self._map_api_error(response.status_code, response.text)

        except httpx.TimeoutException:
            logger.error("WhatsApp request timed out after %ss", self.api_timeout)
            return NotificationSendResult(False, "WhatsApp request timed out")
        except Exception as exc:
            # Redact the access token from any exception text before logging
            logger.error(
                "Failed to send WhatsApp message: %s",
                redact_secrets(str(exc), [self.access_token]),
            )
            return NotificationSendResult(False, "Failed to reach WhatsApp API")

    def _map_api_error(self, status_code: int, body: str) -> NotificationSendResult:
        """Map a Meta Cloud API failure to a safe, useful error message."""
        detail = safe_error_detail(body, [self.access_token])
        detail_lower = (detail or "").lower()

        if status_code == 401:
            error = "WhatsApp access token is invalid or expired"
        elif status_code == 403:
            error = "WhatsApp API access forbidden (check platform app configuration)"
        elif status_code == 429:
            error = "WhatsApp rate limit exceeded, try again later"
        elif "recipient" in detail_lower or "phone number" in detail_lower:
            error = "Invalid WhatsApp recipient phone number"
        else:
            error = "WhatsApp API error"

        # Log the failure factually - never the access token itself
        logger.error(
            "WhatsApp API error: status=%s detail=%s (credentials configured: %s)",
            status_code,
            detail,
            bool(self.phone_number_id and self.access_token),
        )
        return NotificationSendResult(False, error)
    
    async def send_test(self, recipient: str) -> bool:
        """Send test WhatsApp message."""
        return await self.send(
            recipient=recipient,
            title="Test Notification",
            message="This is a test notification from DevOps Monitor Pro. Your WhatsApp configuration is working correctly.",
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
        """Format message for WhatsApp."""
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "high": "🔶",
            "critical": "🔴"
        }
        emoji = severity_emoji.get(severity.lower(), "⚡")
        
        formatted = f"{emoji} *{severity.upper()}* {title}\n\n{message}"
        
        if metadata:
            formatted += "\n\n📋 Details:"
            for key, value in metadata.items():
                if key != "test":
                    formatted += f"\n• {key}: {value}"
            formatted += f"\n\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return formatted