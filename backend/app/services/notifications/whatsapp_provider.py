"""
WhatsApp notification provider using WhatsApp Business API.
"""
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from .base import NotificationProvider

logger = logging.getLogger("devops_monitor")


class WhatsAppProvider(NotificationProvider):
    """WhatsApp notification provider using WhatsApp Business API."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("whatsapp_api_url", "https://graph.facebook.com/v17.0")
        self.phone_number_id = config.get("whatsapp_phone_number_id", "")
        self.access_token = config.get("whatsapp_access_token", "")
        self.api_timeout = config.get("whatsapp_timeout", 30)
    
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
        
        if not self.phone_number_id or not self.access_token:
            logger.error("WhatsApp provider is missing phone_number_id or access_token")
            return False
        
        try:
            # Format recipient phone number (remove + if present, ensure country code)
            phone_number = recipient.replace("+", "").strip()
            
            # Create message payload
            payload = {
                "messaging_product": "messages",
                "to": phone_number,
                "type": "text",
                "text": {
                    "body": self._format_message(title, message, severity, metadata)
                }
            }
            
            # Send to WhatsApp Business API
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"WhatsApp message sent successfully to {phone_number}")
                    return True
                else:
                    logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {recipient}: {e}")
            return False
    
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