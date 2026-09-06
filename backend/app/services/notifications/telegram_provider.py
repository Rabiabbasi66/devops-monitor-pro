"""
Telegram notification provider using Telegram Bot API.
"""
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from .base import NotificationProvider

logger = logging.getLogger("devops_monitor")


class TelegramProvider(NotificationProvider):
    """Telegram notification provider using Telegram Bot API."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get("telegram_bot_token", "")
        self.api_timeout = config.get("telegram_timeout", 30)
        self.parse_mode = config.get("telegram_parse_mode", "HTML")
    
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
        
        if not self.bot_token:
            logger.error("Telegram provider is missing bot_token")
            return False
        
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
                        logger.info(f"Telegram message sent successfully to chat_id {recipient}")
                        return True
                    else:
                        logger.error(f"Telegram API returned error: {result.get('description')}")
                        return False
                else:
                    logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {recipient}: {e}")
            return False
    
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