import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from ..models.alert import Alert
from ..models.notification import Notification, NotificationType
from ..models.notification_settings import NotificationChannelConfig, NotificationProviderType
from ..models.server import Server
from ..config import settings

logger = logging.getLogger("devops_monitor")


class NotificationService:
    def __init__(self):
        # Lazy import providers to avoid circular dependencies
        self._providers = None
        self._provider_configs = {}
    
    def _get_providers(self) -> Dict[str, Any]:
        """Lazy load and initialize notification providers."""
        if self._providers is not None:
            return self._providers
        
        from .notifications import EmailProvider, WhatsAppProvider, TelegramProvider
        
        self._providers = {
            NotificationProviderType.EMAIL: EmailProvider,
            NotificationProviderType.WHATSAPP: WhatsAppProvider,
            NotificationProviderType.TELEGRAM: TelegramProvider,
        }
        
        # Provider configurations from environment
        self._provider_configs = {
            NotificationProviderType.EMAIL: {
                "enabled": settings.SMTP_ENABLED if hasattr(settings, "SMTP_ENABLED") else False,
                "smtp_server": getattr(settings, "SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": getattr(settings, "SMTP_PORT", 587),
                "smtp_username": getattr(settings, "SMTP_USERNAME", ""),
                "smtp_password": getattr(settings, "SMTP_PASSWORD", ""),
                "smtp_use_tls": getattr(settings, "SMTP_USE_TLS", True),
                "smtp_from_email": getattr(settings, "SMTP_FROM_EMAIL", ""),
                "smtp_from_name": getattr(settings, "SMTP_FROM_NAME", "DevOps Monitor Pro"),
            },
            NotificationProviderType.WHATSAPP: {
                "enabled": settings.WHATSAPP_ENABLED if hasattr(settings, "WHATSAPP_ENABLED") else False,
                "whatsapp_api_url": getattr(settings, "WHATSAPP_API_URL", "https://graph.facebook.com/v17.0"),
                "whatsapp_phone_number_id": getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", ""),
                "whatsapp_access_token": getattr(settings, "WHATSAPP_ACCESS_TOKEN", ""),
                "whatsapp_timeout": getattr(settings, "WHATSAPP_TIMEOUT", 30),
            },
            NotificationProviderType.TELEGRAM: {
                "enabled": settings.TELEGRAM_ENABLED if hasattr(settings, "TELEGRAM_ENABLED") else False,
                "telegram_bot_token": getattr(settings, "TELEGRAM_BOT_TOKEN", ""),
                "telegram_timeout": getattr(settings, "TELEGRAM_TIMEOUT", 30),
                "telegram_parse_mode": getattr(settings, "TELEGRAM_PARSE_MODE", "HTML"),
            },
        }
        
        return self._providers
    
    async def create_for_alert(self, server: Server, alert: Alert) -> Notification:
        """Create in-app notification and send external notifications."""
        # Create in-app notification (preserving existing functionality)
        notification = Notification(
            user_id=server.user_id,
            alert_id=str(alert.id),
            type=NotificationType.ALERT,
            title=f"{alert.severity.value.upper()} Alert: {server.name}",
            message=alert.message,
        )
        await notification.insert()
        
        # Send external notifications
        await self._send_external_notifications(
            server=server,
            alert=alert,
            notification_type="alert",
            title=notification.title,
            message=notification.message,
            severity=alert.severity.value
        )
        
        return notification

    async def create_recovery(self, server: Server) -> Notification:
        """Create recovery notification and send external notifications."""
        # Create in-app notification (preserving existing functionality)
        notification = Notification(
            user_id=server.user_id,
            type=NotificationType.RECOVERY,
            title=f"Server Recovered: {server.name}",
            message=f"{server.name} is back online",
        )
        await notification.insert()
        
        # Send external notifications
        await self._send_external_notifications(
            server=server,
            alert=None,
            notification_type="recovery",
            title=notification.title,
            message=notification.message,
            severity="info"
        )
        
        return notification

    async def list_for_user(
        self, user_id: str, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        query = Notification.find(Notification.user_id == user_id)
        if unread_only:
            query = query.find(Notification.read == False)  # noqa: E712
        return await query.sort(-Notification.created_at).limit(limit).to_list()

    async def mark_read(self, notification_id: str, user_id: str) -> Notification | None:
        from beanie import PydanticObjectId

        try:
            notification = await Notification.get(PydanticObjectId(notification_id))
        except Exception:
            return None
        if not notification or notification.user_id != user_id:
            return None
        notification.read = True
        await notification.save()
        return notification
    
    async def _send_external_notifications(
        self,
        server: Server,
        alert: Optional[Alert],
        notification_type: str,
        title: str,
        message: str,
        severity: str
    ) -> None:
        """Send notifications through configured external channels."""
        try:
            # Get user's notification channel configurations
            channels = await NotificationChannelConfig.find(
                NotificationChannelConfig.user_id == server.user_id,
                NotificationChannelConfig.enabled == True
            ).to_list()
            
            if not channels:
                logger.debug(f"No notification channels configured for user {server.user_id}")
                return
            
            providers = self._get_providers()
            
            for channel in channels:
                # Check cooldown
                if not self._should_send_notification(channel):
                    logger.debug(f"Notification to {channel.provider} skipped due to cooldown")
                    continue
                
                # Check if notification type and severity match
                if not self._should_send_for_channel(channel, notification_type, severity):
                    logger.debug(f"Notification to {channel.provider} skipped due to type/severity filter")
                    continue
                
                # Get provider instance
                provider_class = providers.get(channel.provider)
                if not provider_class:
                    logger.warning(f"Provider {channel.provider} not found")
                    continue
                
                provider = provider_class(self._provider_configs[channel.provider])
                
                # Prepare metadata
                metadata = {
                    "server_name": server.name,
                    "server_id": str(server.id),
                    "notification_type": notification_type,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                if alert:
                    metadata.update({
                        "alert_id": str(alert.id),
                        "metric_type": alert.metric_type,
                        "current_value": alert.current_value,
                        "threshold": alert.threshold,
                    })
                
                # Send notification
                success = await provider.send(
                    recipient=channel.recipient,
                    title=title,
                    message=message,
                    severity=severity,
                    metadata=metadata
                )
                
                if success:
                    # Update last sent time
                    channel.last_sent_at = datetime.utcnow()
                    await channel.save()
                    logger.info(f"External notification sent via {channel.provider} to {channel.recipient}")
                else:
                    logger.error(f"Failed to send notification via {channel.provider}")
                    
        except Exception as e:
            logger.exception(f"Error sending external notifications: {e}")
    
    def _should_send_notification(self, channel: NotificationChannelConfig) -> bool:
        """Check if notification should be sent based on cooldown."""
        if not channel.last_sent_at:
            return True
        
        cooldown = timedelta(seconds=channel.cooldown_seconds)
        time_since_last = datetime.utcnow() - channel.last_sent_at
        
        return time_since_last >= cooldown
    
    def _should_send_for_channel(
        self,
        channel: NotificationChannelConfig,
        notification_type: str,
        severity: str
    ) -> bool:
        """Check if notification should be sent based on channel filters."""
        # Check notification type
        if notification_type not in channel.notification_types:
            return False
        
        # Check severity
        severity_order = {
            "info": 0,
            "warning": 1,
            "high": 2,
            "critical": 3
        }
        
        try:
            current_level = severity_order.get(severity.lower(), 0)
            min_level = severity_order.get(channel.min_severity.lower(), 0)
            return current_level >= min_level
        except Exception:
            logger.error(f"Invalid severity comparison: {severity} vs {channel.min_severity}")
            return False
    
    async def create_notification_channel(
        self,
        user_id: str,
        channel_data: Dict[str, Any]
    ) -> NotificationChannelConfig:
        """Create a notification channel configuration."""
        channel = NotificationChannelConfig(
            user_id=user_id,
            **channel_data
        )
        await channel.insert()
        return channel
    
    async def get_user_channels(
        self,
        user_id: str
    ) -> List[NotificationChannelConfig]:
        """Get all notification channels for a user."""
        return await NotificationChannelConfig.find(
            NotificationChannelConfig.user_id == user_id
        ).to_list()
    
    async def update_notification_channel(
        self,
        channel: NotificationChannelConfig,
        update_data: Dict[str, Any]
    ) -> NotificationChannelConfig:
        """Update a notification channel configuration."""
        for key, value in update_data.items():
            if value is not None:
                setattr(channel, key, value)
        channel.updated_at = datetime.utcnow()
        await channel.save()
        return channel
    
    async def delete_notification_channel(
        self,
        channel: NotificationChannelConfig
    ) -> None:
        """Delete a notification channel configuration."""
        await channel.delete()
    
    async def send_test_notification(
        self,
        user_id: str,
        provider: NotificationProviderType,
        recipient: str
    ) -> Dict[str, Any]:
        """Send a test notification through a specific provider."""
        providers = self._get_providers()
        provider_class = providers.get(provider)
        
        if not provider_class:
            return {"success": False, "error": f"Provider {provider} not found"}
        
        provider = provider_class(self._provider_configs[provider])
        
        success = await provider.send_test(recipient)
        
        return {
            "success": success,
            "provider": provider,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat()
        }
