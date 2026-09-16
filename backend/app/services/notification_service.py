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
from ..models.email_verification import (
    EmailVerification,
    generate_verification_code,
    hash_verification_code,
)
from ..utils.secret_masking import redact_secrets
from ..config import settings

logger = logging.getLogger("devops_monitor")


class NotificationService:
    def __init__(self):
        self._providers = None
        self._provider_configs = {}
    
    def _get_providers(self) -> Dict[str, Any]:
        """Lazy load provider classes and build platform infrastructure configuration."""
        if self._providers is None:
            from .notifications import EmailProvider

            self._providers = {
                NotificationProviderType.EMAIL: EmailProvider,
            }

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
    # Email verification (platform-managed SMTP)
    # ------------------------------------------------------------------

    async def request_email_verification(self, user_id: str, email: str) -> Dict[str, Any]:
        """Request an email verification code.

        Generates a 6-digit code, stores its hash, and sends it via the
        configured SMTP provider. Codes expire in 10 minutes and are single-use.
        """
        # Validate email format
        from ..utils.validators import validate_email_format
        if not validate_email_format(email):
            return {"success": False, "error": "Invalid email address"}

        # Check if SMTP is configured
        self._get_providers()
        email_config = self._provider_configs.get(NotificationProviderType.EMAIL, {})
        email_provider_class = self._providers.get(NotificationProviderType.EMAIL)
        # Instantiate the provider BEFORE sending: _providers maps provider type
        # -> CLASS, so the send call below must run on a real instance.
        email_provider = email_provider_class(email_config) if email_provider_class else None
        if not email_provider or not email_config.get("enabled", False):
            missing = email_provider.missing_config() if email_provider else "Email provider not available"
            return {"success": False, "error": missing or "Email provider is not configured"}

        # Delete any existing unused verification codes for this user/email
        await EmailVerification.find(
            EmailVerification.user_id == user_id,
            EmailVerification.email == email,
            EmailVerification.used == False
        ).delete_many()

        # Generate and store verification code
        raw_code = generate_verification_code()
        verification = EmailVerification(
            user_id=user_id,
            email=email,
            code_hash=hash_verification_code(raw_code),
            expires_at=EmailVerification.build_expiry(minutes=10),
        )
        await verification.insert()

        # Send verification email
        result = await email_provider.send_with_result(
            recipient=email,
            title="Email Verification Code",
            message=f"Your verification code is: {raw_code}\n\nThis code expires in 10 minutes.",
            severity="info",
            metadata={"verification": True, "timestamp": datetime.utcnow().isoformat()}
        )

        if result.success:
            logger.info("Verification code sent to %s for user %s", email, user_id)
            return {"success": True, "message": "Verification code sent to your email"}
        else:
            await verification.delete()
            logger.error("Failed to send verification code to %s: %s", email, result.error)
            return {"success": False, "error": result.error or "Failed to send verification email"}

    async def verify_email_code(self, user_id: str, email: str, code: str) -> Dict[str, Any]:
        """Verify an email verification code.

        Validates the code against the stored hash, checks expiration and
        single-use status, and marks the code as used on success.
        """
        if not code or len(code) != 6 or not code.isdigit():
            return {"success": False, "error": "Invalid verification code format"}

        code_hash = hash_verification_code(code)
        verification = await EmailVerification.find_one(
            EmailVerification.user_id == user_id,
            EmailVerification.email == email,
            EmailVerification.code_hash == code_hash,
            EmailVerification.used == False
        )

        if not verification:
            return {"success": False, "error": "Invalid verification code"}

        if verification.is_expired():
            await verification.delete()
            return {"success": False, "error": "Verification code has expired"}

        # Mark as used
        verification.used = True
        verification.used_at = datetime.utcnow()
        await verification.save()

        # Create or update the email notification channel
        existing = await NotificationChannelConfig.find_one(
            NotificationChannelConfig.user_id == user_id,
            NotificationChannelConfig.provider == NotificationProviderType.EMAIL,
        )
        if existing:
            existing.recipient = email
            existing.enabled = True
            existing.updated_at = datetime.utcnow()
            await existing.save()
        else:
            await NotificationChannelConfig(
                user_id=user_id,
                provider=NotificationProviderType.EMAIL,
                recipient=email,
                enabled=True,
                min_severity="warning",
                notification_types=["alert", "recovery", "offline"],
                cooldown_seconds=300,
            ).insert()

        logger.info("Email verified for user %s: %s", user_id, email)
        return {"success": True, "verified": True, "message": "Email verified successfully"}
