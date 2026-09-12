import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from ..models.alert import Alert
from ..models.notification import Notification, NotificationType
from ..models.notification_settings import (
    NotificationChannelConfig,
    NotificationProviderType,
    sanitize_provider_metadata,
)
from ..models.server import Server
from ..models.telegram_connection import (
    TelegramConnectionToken,
    generate_connection_token,
    hash_connection_token,
)
from ..utils.secret_masking import redact_secrets
from ..config import settings

logger = logging.getLogger("devops_monitor")


class NotificationService:
    def __init__(self):
        # Lazy import providers to avoid circular dependencies
        self._providers = None
        self._provider_configs = {}
        self._telegram_bot_username: Optional[str] = None
    
    def _get_providers(self) -> Dict[str, Any]:
        """Lazy load provider classes and (re)build platform infrastructure
        configuration from settings.

        Configuration is re-read on every call so environment (.env) values
        are always authoritative and provider enablement is never hard-coded.
        Provider configs hold platform credentials only - user channel
        documents never contain them.
        """
        if self._providers is None:
            from .notifications import EmailProvider, WhatsAppProvider, TelegramProvider

            self._providers = {
                NotificationProviderType.EMAIL: EmailProvider,
                NotificationProviderType.WHATSAPP: WhatsAppProvider,
                NotificationProviderType.TELEGRAM: TelegramProvider,
            }

        # Provider infrastructure configurations from environment (platform-level)
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

    # ------------------------------------------------------------------
    # Platform provider status (booleans only - never secret values)
    # ------------------------------------------------------------------

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Report platform-level provider availability.

        Returns only booleans and static messages; no credential values are
        ever included, so the response is safe for frontend display.
        """
        self._get_providers()
        status: Dict[str, Dict[str, Any]] = {}

        for provider_type in NotificationProviderType:
            config = self._provider_configs.get(provider_type, {})
            provider_class = self._providers.get(provider_type)
            enabled = bool(config.get("enabled", False))
            provider = provider_class(config) if provider_class else None
            missing = provider.missing_config() if provider else "Provider is not available"
            configured = provider is not None and missing is None

            if not enabled or not configured:
                status[provider_type.value] = {
                    "enabled": enabled,
                    "configured": configured,
                    "available": False,
                    "message": "Platform configuration unavailable. Contact administrator.",
                }
            else:
                status[provider_type.value] = {
                    "enabled": True,
                    "configured": True,
                    "available": True,
                    "message": "Available",
                }

        return status

    def validate_recipient_for_provider(
        self, provider: NotificationProviderType, recipient: str
    ) -> Optional[str]:
        """Validate a recipient format for the given provider (no secrets)."""
        self._get_providers()
        provider_class = self._providers.get(provider)
        if not provider_class:
            return f"Provider {provider} is not supported"
        return provider_class(self._provider_configs.get(provider, {})).validate_recipient(recipient)
    
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
                # Failure isolation: one broken channel must never block others
                try:
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
                    
                    # Send notification (detailed result never contains secrets)
                    result = await provider.send_with_result(
                        recipient=channel.recipient,
                        title=title,
                        message=message,
                        severity=severity,
                        metadata=metadata
                    )
                    
                    if result.success:
                        # Update last sent time
                        channel.last_sent_at = datetime.utcnow()
                        await channel.save()
                        logger.info(f"External notification sent via {channel.provider} to {channel.recipient}")
                    else:
                        logger.error(
                            f"Failed to send notification via {channel.provider}: "
                            f"{result.error or 'unknown error'}"
                        )
                except Exception as channel_error:
                    # Isolate the failure and continue with the remaining channels
                    logger.exception(
                        f"Error sending notification via {channel.provider}: {channel_error}"
                    )
                    continue
                    
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
        """Send a test notification through a specific provider.

        Validation stages (in order):
        1. Provider is known
        2. Platform infrastructure is enabled for the provider
        3. Required platform configuration is present
        4. Recipient is valid for the provider
        5. Provider API reports success

        Error responses are useful but never expose credentials.
        """
        providers = self._get_providers()
        provider_value = provider.value if hasattr(provider, "value") else str(provider)
        provider_class = providers.get(provider)

        if not provider_class:
            return {
                "success": False,
                "provider": provider_value,
                "recipient": recipient,
                "error": f"Provider {provider_value} is not supported",
            }

        config = self._provider_configs.get(provider, {})
        provider_instance = provider_class(config)

        if not provider_instance.is_enabled():
            return {
                "success": False,
                "provider": provider_value,
                "recipient": recipient,
                "error": f"{provider_value.capitalize()} provider is not enabled",
            }

        missing = provider_instance.missing_config()
        if missing:
            # Static, secret-free message built by the provider
            return {
                "success": False,
                "provider": provider_value,
                "recipient": recipient,
                "error": missing,
            }

        recipient_error = provider_instance.validate_recipient(recipient)
        if recipient_error:
            return {
                "success": False,
                "provider": provider_value,
                "recipient": recipient,
                "error": recipient_error,
            }

        result = await provider_instance.send_with_result(
            recipient=recipient,
            title="Test Notification",
            message="This is a test notification from DevOps Monitor Pro. Your configuration is working correctly.",
            severity="info",
            metadata={"test": True, "timestamp": datetime.utcnow().isoformat()},
        )

        response = {
            "success": result.success,
            "provider": provider_value,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if not result.success:
            response["error"] = result.error or f"Failed to send test notification via {provider_value}"
        return response

    # ------------------------------------------------------------------
    # Multi-tenancy: ownership-scoped channel lookup
    # ------------------------------------------------------------------

    async def get_user_channel(
        self, user_id: str, channel_id: str
    ) -> Optional[NotificationChannelConfig]:
        """Fetch a channel only when it belongs to the given user."""
        try:
            from beanie import PydanticObjectId

            oid = PydanticObjectId(channel_id)
        except Exception:
            return None
        channel = await NotificationChannelConfig.get(oid)
        if not channel or channel.user_id != user_id:
            return None
        return channel

    # ------------------------------------------------------------------
    # Telegram connection (platform-managed bot onboarding)
    # ------------------------------------------------------------------

    def _telegram_ready(self) -> bool:
        """Whether the platform Telegram infrastructure is usable."""
        self._get_providers()
        from .notifications import TelegramProvider

        config = self._provider_configs.get(NotificationProviderType.TELEGRAM, {})
        provider = TelegramProvider(config)
        return provider.is_enabled() and provider.missing_config() is None

    async def _get_telegram_bot_username(self) -> Optional[str]:
        """Resolve the platform bot username via getMe (cached, no secrets)."""
        if self._telegram_bot_username:
            return self._telegram_bot_username
        if getattr(settings, "TELEGRAM_BOT_USERNAME", ""):
            self._telegram_bot_username = settings.TELEGRAM_BOT_USERNAME
            return self._telegram_bot_username

        self._get_providers()
        token = self._provider_configs.get(NotificationProviderType.TELEGRAM, {}).get(
            "telegram_bot_token", ""
        )
        if not token:
            return None
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                if resp.status_code == 200 and resp.json().get("ok"):
                    self._telegram_bot_username = resp.json()["result"].get("username")
                    return self._telegram_bot_username
                logger.error("Telegram getMe failed: status=%s", resp.status_code)
        except Exception as exc:
            # Never log the token (it is part of the request URL)
            logger.error("Telegram getMe failed: %s", redact_secrets(str(exc), [token]))
        return None

    async def create_telegram_connect_token(self, user_id: str) -> Dict[str, Any]:
        """Create a one-time Telegram connection token for a user.

        The raw token is returned once (to build the t.me deep link); only its
        SHA-256 hash is stored. Tokens expire, are single-use, and never
        contain user information.
        """
        if not self._telegram_ready():
            return {"success": False, "error": "Telegram provider is not available"}

        raw_token = generate_connection_token()
        record = TelegramConnectionToken(
            user_id=user_id,
            token_hash=hash_connection_token(raw_token),
            expires_at=TelegramConnectionToken.build_expiry(),
        )
        await record.insert()

        bot_username = await self._get_telegram_bot_username()
        connect_url = f"https://t.me/{bot_username}?start={raw_token}" if bot_username else None

        return {
            "success": True,
            "token": raw_token,
            "bot_username": bot_username,
            "connect_url": connect_url,
            "expires_at": record.expires_at.isoformat(),
        }

    async def complete_telegram_connect(
        self, raw_token: str, chat_id: str, telegram_username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Map a Telegram chat_id to the user that owns ``raw_token``.

        Called by the platform bot webhook after the user sends
        ``/start <token>``. The token is single-use and must not be expired.
        """
        if not raw_token or not chat_id:
            return {"success": False, "error": "Missing connection token or chat id"}

        token_hash = hash_connection_token(raw_token)
        record = await TelegramConnectionToken.find_one(
            TelegramConnectionToken.token_hash == token_hash
        )
        if not record:
            return {"success": False, "error": "Invalid connection token"}
        if record.used:
            return {"success": False, "error": "Connection token has already been used"}
        if record.is_expired():
            await record.delete()
            return {"success": False, "error": "Connection token has expired"}

        record.used = True
        record.used_at = datetime.utcnow()
        record.chat_id = str(chat_id)
        record.telegram_username = telegram_username
        await record.save()

        # Safe identifiers only - never secrets
        metadata = sanitize_provider_metadata(
            {"chat_id": str(chat_id), "telegram_username": telegram_username}
        )

        existing = await NotificationChannelConfig.find_one(
            NotificationChannelConfig.user_id == record.user_id,
            NotificationChannelConfig.provider == NotificationProviderType.TELEGRAM,
        )
        if existing:
            existing.recipient = str(chat_id)
            existing.provider_metadata = metadata
            existing.enabled = True
            existing.updated_at = datetime.utcnow()
            await existing.save()
        else:
            await NotificationChannelConfig(
                user_id=record.user_id,
                provider=NotificationProviderType.TELEGRAM,
                recipient=str(chat_id),
                enabled=True,
                provider_metadata=metadata,
            ).insert()

        logger.info("Telegram connection completed for user %s", record.user_id)
        return {"success": True, "user_id": record.user_id, "chat_id": str(chat_id)}

    async def get_telegram_connect_status(self, user_id: str, raw_token: str) -> Dict[str, Any]:
        """Check whether a pending connection token has been completed.

        Ownership: the token record must belong to ``user_id``.
        """
        if not raw_token:
            return {"connected": False, "error": "Connection token is required"}

        token_hash = hash_connection_token(raw_token)
        record = await TelegramConnectionToken.find_one(
            TelegramConnectionToken.token_hash == token_hash
        )
        if not record or record.user_id != user_id:
            return {"connected": False, "error": "Invalid connection token"}
        if record.used:
            return {
                "connected": True,
                "chat_id": record.chat_id,
                "telegram_username": record.telegram_username,
            }
        if record.is_expired():
            return {
                "connected": False,
                "expired": True,
                "error": "Connection token has expired",
            }
        return {
            "connected": False,
            "pending": True,
            "expires_at": record.expires_at.isoformat(),
        }

    async def disconnect_telegram(self, user_id: str) -> Dict[str, Any]:
        """Remove the user's Telegram channel(s)."""
        channels = await NotificationChannelConfig.find(
            NotificationChannelConfig.user_id == user_id,
            NotificationChannelConfig.provider == NotificationProviderType.TELEGRAM,
        ).to_list()
        for channel in channels:
            await channel.delete()
        return {
            "success": True,
            "disconnected": len(channels) > 0,
            "channels_removed": len(channels),
        }
