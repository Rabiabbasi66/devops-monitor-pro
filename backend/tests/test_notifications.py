"""
Unit tests for notification providers and notification service.
Note: Integration tests requiring MongoDB are skipped due to pre-existing test infrastructure issues.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notifications.base import NotificationProvider, NotificationChannel
from app.services.notifications.email_provider import EmailProvider
from app.services.notifications.whatsapp_provider import WhatsAppProvider
from app.services.notifications.telegram_provider import TelegramProvider
from app.services.notification_service import NotificationService
from app.models.notification_settings import NotificationProviderType


class TestNotificationProviderBase:
    """Test base notification provider functionality."""
    
    def test_notification_channel_severity_filter(self):
        """Test notification channel severity filtering."""
        channel = NotificationChannel(
            provider="email",
            enabled=True,
            recipient="test@example.com",
            min_severity="warning",
            notification_types=["alert", "recovery"]
        )
        
        # Should send for warning and above
        assert channel.should_send("alert", "warning") is True
        assert channel.should_send("alert", "high") is True
        assert channel.should_send("alert", "critical") is True
        
        # Should not send for info
        assert channel.should_send("alert", "info") is False
    
    def test_notification_channel_type_filter(self):
        """Test notification channel type filtering."""
        channel = NotificationChannel(
            provider="email",
            enabled=True,
            recipient="test@example.com",
            min_severity="info",
            notification_types=["alert", "recovery"]
        )
        
        # Should send for configured types
        assert channel.should_send("alert", "warning") is True
        assert channel.should_send("recovery", "info") is True
        
        # Should not send for other types
        assert channel.should_send("offline", "critical") is False
        assert channel.should_send("security", "high") is False
    
    def test_notification_channel_disabled(self):
        """Test disabled channel does not send."""
        channel = NotificationChannel(
            provider="email",
            enabled=False,
            recipient="test@example.com",
            min_severity="info",
            notification_types=["alert"]
        )
        
        assert channel.should_send("alert", "critical") is False


class TestEmailProvider:
    """Test email notification provider."""
    
    def test_email_provider_initialization(self):
        """Test email provider initialization."""
        config = {
            "enabled": True,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "test@example.com",
            "smtp_password": "password",
            "smtp_from_email": "test@example.com",
            "smtp_from_name": "DevOps Monitor Pro"
        }
        provider = EmailProvider(config)
        
        assert provider.enabled is True
        assert provider.smtp_server == "smtp.gmail.com"
        assert provider.smtp_port == 587
    
    def test_email_provider_disabled(self):
        """Test disabled email provider."""
        config = {"enabled": False}
        provider = EmailProvider(config)
        
        assert provider.enabled is False
        assert provider.is_enabled() is False
    
    @pytest.mark.asyncio
    async def test_email_provider_send_disabled(self):
        """Test send returns False when disabled."""
        config = {"enabled": False}
        provider = EmailProvider(config)
        
        result = await provider.send(
            recipient="test@example.com",
            title="Test",
            message="Test message",
            severity="info"
        )
        
        assert result is False


class TestWhatsAppProvider:
    """Test WhatsApp notification provider."""
    
    def test_whatsapp_provider_initialization(self):
        """Test WhatsApp provider initialization."""
        config = {
            "enabled": True,
            "whatsapp_api_url": "https://graph.facebook.com/v17.0",
            "whatsapp_phone_number_id": "123456789",
            "whatsapp_access_token": "test_token"
        }
        provider = WhatsAppProvider(config)
        
        assert provider.enabled is True
        assert provider.phone_number_id == "123456789"
    
    def test_whatsapp_provider_disabled(self):
        """Test disabled WhatsApp provider."""
        config = {"enabled": False}
        provider = WhatsAppProvider(config)
        
        assert provider.enabled is False
    
    @pytest.mark.asyncio
    async def test_whatsapp_provider_send_disabled(self):
        """Test send returns False when disabled."""
        config = {"enabled": False}
        provider = WhatsAppProvider(config)
        
        result = await provider.send(
            recipient="+1234567890",
            title="Test",
            message="Test message",
            severity="info"
        )
        
        assert result is False


class TestTelegramProvider:
    """Test Telegram notification provider."""
    
    def test_telegram_provider_initialization(self):
        """Test Telegram provider initialization."""
        config = {
            "enabled": True,
            "telegram_bot_token": "test_token",
            "telegram_parse_mode": "HTML"
        }
        provider = TelegramProvider(config)
        
        assert provider.enabled is True
        assert provider.bot_token == "test_token"
    
    def test_telegram_provider_disabled(self):
        """Test disabled Telegram provider."""
        config = {"enabled": False}
        provider = TelegramProvider(config)
        
        assert provider.enabled is False
    
    @pytest.mark.asyncio
    async def test_telegram_provider_send_disabled(self):
        """Test send returns False when disabled."""
        config = {"enabled": False}
        provider = TelegramProvider(config)
        
        result = await provider.send(
            recipient="123456789",
            title="Test",
            message="Test message",
            severity="info"
        )
        
        assert result is False


class TestNotificationService:
    """Test notification service unit tests."""
    
    def test_service_initialization(self):
        """Test notification service can be initialized."""
        service = NotificationService()
        assert service is not None
        assert hasattr(service, 'create_for_alert')
        assert hasattr(service, 'create_recovery')
        assert hasattr(service, 'list_for_user')
        assert hasattr(service, 'mark_read')
    
    @pytest.mark.asyncio
    async def test_send_test_notification(self):
        """Test sending a test notification."""
        service = NotificationService()
        
        result = await service.send_test_notification(
            user_id="user123",
            provider=NotificationProviderType.EMAIL,
            recipient="test@example.com"
        )
        
        # Should return result dict with success status
        assert "success" in result
        assert "provider" in result
        assert "recipient" in result
    
    def test_severity_ordering(self):
        """Test severity comparison logic."""
        service = NotificationService()
        
        # Test cooldown check with no last_sent
        mock_channel = MagicMock()
        mock_channel.last_sent_at = None
        mock_channel.cooldown_seconds = 300
        
        assert service._should_send_notification(mock_channel) is True
    
    def test_notification_service_preserves_existing_methods(self):
        """Test that existing methods are still present."""
        service = NotificationService()
        
        # Verify all existing methods are still present
        assert hasattr(service, 'create_for_alert')
        assert hasattr(service, 'create_recovery')
        assert hasattr(service, 'list_for_user')
        assert hasattr(service, 'mark_read')
        
        # Verify new methods are present
        assert hasattr(service, 'create_notification_channel')
        assert hasattr(service, 'get_user_channels')
        assert hasattr(service, 'update_notification_channel')
        assert hasattr(service, 'delete_notification_channel')
        assert hasattr(service, 'send_test_notification')


# ===========================================================================
# Multi-tenant SaaS notification architecture tests
# ===========================================================================
import json  # noqa: E402
import logging  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

from app.config import settings  # noqa: E402
from app.models.notification_settings import (  # noqa: E402
    NotificationChannelConfig,
    sanitize_provider_metadata,
)
from app.models.telegram_connection import (  # noqa: E402
    TelegramConnectionToken,
    generate_connection_token,
    hash_connection_token,
)
from app.services.notifications.base import NotificationSendResult  # noqa: E402

WHATSAPP_TOKEN = "EAAB-super-secret-token-xyz"
TELEGRAM_TOKEN = "123456:ABC-super-secret-bot-token"
SMTP_PASSWORD = "super-secret-smtp-password"


def _email_config(**overrides):
    config = {
        "enabled": True,
        "smtp_server": "smtp.test.local",
        "smtp_port": 587,
        "smtp_username": "platform@example.com",
        "smtp_password": SMTP_PASSWORD,
        "smtp_use_tls": True,
        "smtp_from_email": "platform@example.com",
        "smtp_from_name": "DevOps Monitor Pro",
    }
    config.update(overrides)
    return config


def _whatsapp_config(**overrides):
    config = {
        "enabled": True,
        "whatsapp_api_url": "https://graph.facebook.com/v17.0",
        "whatsapp_phone_number_id": "1234567890",
        "whatsapp_access_token": WHATSAPP_TOKEN,
        "whatsapp_timeout": 30,
    }
    config.update(overrides)
    return config


def _telegram_config(**overrides):
    config = {
        "enabled": True,
        "telegram_bot_token": TELEGRAM_TOKEN,
        "telegram_timeout": 30,
        "telegram_parse_mode": "HTML",
    }
    config.update(overrides)
    return config


class TestProviderEnablement:
    """Providers must honour enabled/disabled state from platform config."""

    @pytest.mark.asyncio
    async def test_email_provider_enabled(self):
        provider = EmailProvider(_email_config())
        assert provider.is_enabled() is True
        assert provider.missing_config() is None

    @pytest.mark.asyncio
    async def test_email_provider_disabled(self):
        provider = EmailProvider(_email_config(enabled=False))
        assert provider.is_enabled() is False
        result = await provider.send_with_result("a@example.com", "t", "m", "info")
        assert result.success is False
        assert await provider.send("a@example.com", "t", "m", "info") is False

    @pytest.mark.asyncio
    async def test_telegram_provider_enabled(self):
        provider = TelegramProvider(_telegram_config())
        assert provider.is_enabled() is True
        assert provider.missing_config() is None

    @pytest.mark.asyncio
    async def test_telegram_provider_disabled(self):
        provider = TelegramProvider(_telegram_config(enabled=False))
        assert provider.is_enabled() is False
        result = await provider.send_with_result("123456789", "t", "m", "info")
        assert result.success is False
        assert await provider.send("123456789", "t", "m", "info") is False

    @pytest.mark.asyncio
    async def test_whatsapp_provider_enabled(self):
        provider = WhatsAppProvider(_whatsapp_config())
        assert provider.is_enabled() is True
        assert provider.missing_config() is None
        # E.164 recipient validation
        assert provider.validate_recipient("+923001234567") is None
        assert provider.validate_recipient("+92 300 1234567") is None
        assert provider.validate_recipient("923001234567") is None
        assert provider.validate_recipient("12345") is not None
        assert provider.validate_recipient("not-a-phone") is not None

    @pytest.mark.asyncio
    async def test_whatsapp_provider_disabled(self):
        provider = WhatsAppProvider(_whatsapp_config(enabled=False))
        assert provider.is_enabled() is False
        result = await provider.send_with_result("+923001234567", "t", "m", "info")
        assert result.success is False
        assert await provider.send("+923001234567", "t", "m", "info") is False


class TestMissingProviderConfiguration:
    """Missing platform credentials must produce useful, secret-free errors."""

    @pytest.mark.asyncio
    async def test_missing_whatsapp_credentials(self):
        provider = WhatsAppProvider(
            _whatsapp_config(whatsapp_phone_number_id="", whatsapp_access_token="")
        )
        assert provider.missing_config() == "WhatsApp provider is not configured"
        assert "phone number ID" in WhatsAppProvider(
            _whatsapp_config(whatsapp_phone_number_id="")
        ).missing_config()
        assert "access token" in WhatsAppProvider(
            _whatsapp_config(whatsapp_access_token="")
        ).missing_config()

        service = NotificationService()
        with patch.object(settings, "WHATSAPP_ENABLED", True), \
             patch.object(settings, "WHATSAPP_PHONE_NUMBER_ID", ""), \
             patch.object(settings, "WHATSAPP_ACCESS_TOKEN", ""):
            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.WHATSAPP,
                recipient="+923001234567",
            )
        assert result["success"] is False
        assert "not configured" in result["error"]
        assert WHATSAPP_TOKEN not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_missing_telegram_credentials(self):
        provider = TelegramProvider(_telegram_config(telegram_bot_token=""))
        assert "not configured" in provider.missing_config()

        service = NotificationService()
        with patch.object(settings, "TELEGRAM_ENABLED", True), \
             patch.object(settings, "TELEGRAM_BOT_TOKEN", ""):
            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.TELEGRAM,
                recipient="123456789",
            )
        assert result["success"] is False
        assert "not configured" in result["error"]
        assert TELEGRAM_TOKEN not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_missing_smtp_configuration(self):
        provider = EmailProvider(
            _email_config(smtp_server="", smtp_from_email="", smtp_username="")
        )
        assert "not configured" in provider.missing_config()

        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", True), \
             patch.object(settings, "SMTP_SERVER", ""), \
             patch.object(settings, "SMTP_FROM_EMAIL", ""), \
             patch.object(settings, "SMTP_USERNAME", ""):
            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.EMAIL,
                recipient="client@example.com",
            )
        assert result["success"] is False
        assert "not configured" in result["error"]
        assert SMTP_PASSWORD not in json.dumps(result)


class TestChannelFiltering:
    """Cooldown, severity and notification-type filtering must be preserved."""

    def test_notification_cooldown(self):
        service = NotificationService()
        now = datetime.utcnow()

        # No last_sent_at -> allowed
        fresh = MagicMock(last_sent_at=None, cooldown_seconds=300)
        assert service._should_send_notification(fresh) is True

        # Just sent -> blocked during cooldown
        recent = MagicMock(last_sent_at=now, cooldown_seconds=300)
        assert service._should_send_notification(recent) is False

        # Sent before the cooldown window -> allowed again
        old = MagicMock(last_sent_at=now - timedelta(seconds=301), cooldown_seconds=300)
        assert service._should_send_notification(old) is True

        # Independent cooldown state per channel
        assert service._should_send_notification(recent) is False
        assert service._should_send_notification(old) is True

    def test_severity_filtering(self):
        service = NotificationService()
        channel = MagicMock(notification_types=["alert"], min_severity="warning")
        assert service._should_send_for_channel(channel, "alert", "info") is False
        assert service._should_send_for_channel(channel, "alert", "warning") is True
        assert service._should_send_for_channel(channel, "alert", "high") is True
        assert service._should_send_for_channel(channel, "alert", "critical") is True

        critical_only = MagicMock(notification_types=["alert"], min_severity="critical")
        assert service._should_send_for_channel(critical_only, "alert", "high") is False
        assert service._should_send_for_channel(critical_only, "alert", "critical") is True

        info_plus = MagicMock(notification_types=["recovery"], min_severity="info")
        assert service._should_send_for_channel(info_plus, "recovery", "info") is True

    def test_notification_type_filtering(self):
        service = NotificationService()
        alert_only = MagicMock(notification_types=["alert"], min_severity="info")
        assert service._should_send_for_channel(alert_only, "alert", "critical") is True
        assert service._should_send_for_channel(alert_only, "recovery", "critical") is False
        assert service._should_send_for_channel(alert_only, "offline", "critical") is False

        multi = MagicMock(notification_types=["alert", "recovery", "offline"], min_severity="info")
        assert service._should_send_for_channel(multi, "recovery", "info") is True
        assert service._should_send_for_channel(multi, "security", "info") is False


class TestSendTestNotification:
    """send_test_notification must validate stages and return useful errors."""

    @pytest.mark.asyncio
    async def test_send_test_notification_success(self):
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", True), \
             patch("app.services.notifications.EmailProvider") as MockEmail:
            instance = MockEmail.return_value
            instance.is_enabled.return_value = True
            instance.missing_config.return_value = None
            instance.validate_recipient.return_value = None
            instance.send_with_result = AsyncMock(return_value=NotificationSendResult(True))

            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.EMAIL,
                recipient="client@example.com",
            )

        assert result["success"] is True
        assert result["provider"] == "email"
        assert result["recipient"] == "client@example.com"
        assert "error" not in result
        assert "success" in result and "timestamp" in result

    @pytest.mark.asyncio
    async def test_send_test_notification_provider_failure_no_secrets(self):
        service = NotificationService()
        with patch.object(settings, "WHATSAPP_ENABLED", True), \
             patch.object(settings, "WHATSAPP_PHONE_NUMBER_ID", "1234567890"), \
             patch.object(settings, "WHATSAPP_ACCESS_TOKEN", WHATSAPP_TOKEN), \
             patch("app.services.notifications.WhatsAppProvider") as MockWA:
            instance = MockWA.return_value
            instance.is_enabled.return_value = True
            instance.missing_config.return_value = None
            instance.validate_recipient.return_value = None
            instance.send_with_result = AsyncMock(
                return_value=NotificationSendResult(
                    False, "WhatsApp access token is invalid or expired"
                )
            )

            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.WHATSAPP,
                recipient="+923001234567",
            )

        assert result["success"] is False
        assert result["error"] == "WhatsApp access token is invalid or expired"
        assert WHATSAPP_TOKEN not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_send_test_notification_invalid_recipient(self):
        service = NotificationService()
        with patch.object(settings, "WHATSAPP_ENABLED", True), \
             patch.object(settings, "WHATSAPP_PHONE_NUMBER_ID", "1234567890"), \
             patch.object(settings, "WHATSAPP_ACCESS_TOKEN", WHATSAPP_TOKEN):
            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.WHATSAPP,
                recipient="555-1234",
            )
        assert result["success"] is False
        assert "E.164" in result["error"]


class TestProviderFailureIsolation:
    """One failing provider must never block the other providers."""

    @pytest.mark.asyncio
    async def test_provider_failure_isolation(self):
        service = NotificationService()

        def _channel(provider, recipient):
            channel = MagicMock(
                provider=provider,
                recipient=recipient,
                last_sent_at=None,
                cooldown_seconds=300,
                notification_types=["alert"],
                min_severity="info",
            )
            channel.save = AsyncMock()
            return channel

        email_channel = _channel(NotificationProviderType.EMAIL, "a@example.com")
        wa_channel = _channel(NotificationProviderType.WHATSAPP, "+923001234567")
        tg_channel = _channel(NotificationProviderType.TELEGRAM, "123456789")

        server = MagicMock()
        server.name = "srv"
        server.id = "srvid"
        server.user_id = "user123"

        with patch("app.services.notification_service.NotificationChannelConfig") as MockCfg, \
             patch("app.services.notifications.EmailProvider") as MockEmail, \
             patch("app.services.notifications.WhatsAppProvider") as MockWA, \
             patch("app.services.notifications.TelegramProvider") as MockTG:
            MockCfg.find.return_value = MagicMock(
                to_list=AsyncMock(return_value=[email_channel, wa_channel, tg_channel])
            )
            MockEmail.return_value.send_with_result = AsyncMock(
                return_value=NotificationSendResult(True)
            )
            # WhatsApp explodes unexpectedly mid-delivery
            MockWA.return_value.send_with_result = AsyncMock(side_effect=RuntimeError("boom"))
            MockTG.return_value.send_with_result = AsyncMock(
                return_value=NotificationSendResult(True)
            )

            await service._send_external_notifications(
                server=server,
                alert=None,
                notification_type="alert",
                title="t",
                message="m",
                severity="critical",
            )

        # All three providers were attempted despite WhatsApp raising
        MockEmail.return_value.send_with_result.assert_awaited_once()
        MockWA.return_value.send_with_result.assert_awaited_once()
        MockTG.return_value.send_with_result.assert_awaited_once()
        # Success recorded only for the successful channels
        email_channel.save.assert_awaited_once()
        wa_channel.save.assert_not_awaited()
        tg_channel.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_provider_false_result_does_not_stop_others(self):
        """A provider returning failure (not raising) also must not block others."""
        service = NotificationService()

        def _channel(provider, recipient):
            channel = MagicMock(
                provider=provider,
                recipient=recipient,
                last_sent_at=None,
                cooldown_seconds=300,
                notification_types=["alert"],
                min_severity="info",
            )
            channel.save = AsyncMock()
            return channel

        wa_channel = _channel(NotificationProviderType.WHATSAPP, "+923001234567")
        tg_channel = _channel(NotificationProviderType.TELEGRAM, "123456789")

        server = MagicMock()
        server.name = "srv"
        server.id = "srvid"
        server.user_id = "user123"

        with patch("app.services.notification_service.NotificationChannelConfig") as MockCfg, \
             patch("app.services.notifications.WhatsAppProvider") as MockWA, \
             patch("app.services.notifications.TelegramProvider") as MockTG:
            MockCfg.find.return_value = MagicMock(
                to_list=AsyncMock(return_value=[wa_channel, tg_channel])
            )
            MockWA.return_value.send_with_result = AsyncMock(
                return_value=NotificationSendResult(
                    False, "WhatsApp rate limit exceeded, try again later"
                )
            )
            MockTG.return_value.send_with_result = AsyncMock(
                return_value=NotificationSendResult(True)
            )

            await service._send_external_notifications(
                server=server,
                alert=None,
                notification_type="alert",
                title="t",
                message="m",
                severity="critical",
            )

        MockTG.return_value.send_with_result.assert_awaited_once()
        tg_channel.save.assert_awaited_once()
        wa_channel.save.assert_not_awaited()


class TestChannelOwnershipService:
    """Service-level ownership enforcement (multi-tenancy)."""

    @pytest.mark.asyncio
    async def test_get_user_channel_enforces_ownership(self):
        service = NotificationService()
        channel = MagicMock()
        channel.user_id = "user-a"
        valid_oid = "507f1f77bcf86cd799439011"

        with patch("app.services.notification_service.NotificationChannelConfig") as MockCfg:
            MockCfg.get = AsyncMock(return_value=channel)
            assert await service.get_user_channel("user-a", valid_oid) is channel
            assert await service.get_user_channel("user-b", valid_oid) is None

        # Invalid id format -> None (no exception)
        assert await service.get_user_channel("user-a", "not-an-object-id") is None


class TestSecretSafetyResponses:
    """Secrets must never appear in API responses or channel metadata."""

    @pytest.mark.asyncio
    async def test_provider_status_response_contains_no_secrets(self):
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", True), \
             patch.object(settings, "SMTP_PASSWORD", SMTP_PASSWORD), \
             patch.object(settings, "SMTP_FROM_EMAIL", "platform@example.com"), \
             patch.object(settings, "WHATSAPP_ENABLED", True), \
             patch.object(settings, "WHATSAPP_PHONE_NUMBER_ID", "1234567890"), \
             patch.object(settings, "WHATSAPP_ACCESS_TOKEN", WHATSAPP_TOKEN), \
             patch.object(settings, "TELEGRAM_ENABLED", True), \
             patch.object(settings, "TELEGRAM_BOT_TOKEN", TELEGRAM_TOKEN):
            status = service.get_provider_status()

        serialized = json.dumps(status)
        assert status["email"]["available"] is True
        assert status["whatsapp"]["available"] is True
        assert status["telegram"]["available"] is True
        assert WHATSAPP_TOKEN not in serialized
        assert TELEGRAM_TOKEN not in serialized
        assert SMTP_PASSWORD not in serialized

    @pytest.mark.asyncio
    async def test_provider_status_reports_unavailable_without_secrets(self):
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", False), \
             patch.object(settings, "SMTP_PASSWORD", SMTP_PASSWORD), \
             patch.object(settings, "WHATSAPP_ENABLED", False), \
             patch.object(settings, "WHATSAPP_ACCESS_TOKEN", WHATSAPP_TOKEN):
            status = service.get_provider_status()

        assert status["email"]["available"] is False
        assert status["whatsapp"]["available"] is False
        assert "unavailable" in status["email"]["message"].lower()
        assert WHATSAPP_TOKEN not in json.dumps(status)
        assert SMTP_PASSWORD not in json.dumps(status)

    def test_channel_metadata_never_stores_secrets(self):
        sanitized = sanitize_provider_metadata(
            {
                "chat_id": "123456789",
                "telegram_username": "testuser",
                "access_token": WHATSAPP_TOKEN,
                "bot_token": TELEGRAM_TOKEN,
                "smtp_password": SMTP_PASSWORD,
                "api_key": "key123",
            }
        )
        assert sanitized == {"chat_id": "123456789", "telegram_username": "testuser"}


class TestSecretSafetyLogs:
    """Provider credentials must never appear in log output."""

    @pytest.mark.asyncio
    async def test_whatsapp_token_never_logged(self, caplog):
        provider = WhatsAppProvider(_whatsapp_config())
        caplog.set_level(logging.ERROR, logger="devops_monitor")

        with patch(
            "app.services.notifications.whatsapp_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception(
                "Connection failed for https://graph.facebook.com/v17.0/1234567890/messages "
                f"token={WHATSAPP_TOKEN}"
            )
            result = await provider.send_with_result("+923001234567", "t", "m", "critical")

        assert result.success is False
        assert WHATSAPP_TOKEN not in caplog.text

    @pytest.mark.asyncio
    async def test_telegram_bot_token_never_logged(self, caplog):
        provider = TelegramProvider(_telegram_config())
        caplog.set_level(logging.ERROR, logger="devops_monitor")

        with patch(
            "app.services.notifications.telegram_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception(
                f"Cannot connect to https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            )
            result = await provider.send_with_result("123456789", "t", "m", "critical")

        assert result.success is False
        assert TELEGRAM_TOKEN not in caplog.text

    @pytest.mark.asyncio
    async def test_whatsapp_upstream_error_body_never_logs_token(self, caplog):
        provider = WhatsAppProvider(_whatsapp_config())
        caplog.set_level(logging.ERROR, logger="devops_monitor")

        response = MagicMock(
            status_code=401,
            text='{"error":{"message":"Invalid OAuth access token"}}',
        )

        with patch(
            "app.services.notifications.whatsapp_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            result = await provider.send_with_result("+923001234567", "t", "m", "critical")

        assert result.success is False
        assert "invalid or expired" in result.error
        assert WHATSAPP_TOKEN not in caplog.text


class TestProviderErrorMapping:
    """Upstream provider failures map to specific, secret-free error causes."""

    @pytest.mark.asyncio
    async def test_whatsapp_rate_limit_mapping(self):
        provider = WhatsAppProvider(_whatsapp_config())
        response = MagicMock(status_code=429, text="Too many requests")

        with patch(
            "app.services.notifications.whatsapp_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            result = await provider.send_with_result("+923001234567", "t", "m", "critical")

        assert result.success is False
        assert "rate limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_whatsapp_timeout_mapping(self):
        import httpx

        provider = WhatsAppProvider(_whatsapp_config())

        with patch(
            "app.services.notifications.whatsapp_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            result = await provider.send_with_result("+923001234567", "t", "m", "critical")

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_telegram_blocked_bot_mapping(self):
        provider = TelegramProvider(_telegram_config())
        response = MagicMock(
            status_code=403,
            text='{"ok":false,"error_code":403,"description":"Forbidden: bot was blocked by the user"}',
        )

        with patch(
            "app.services.notifications.telegram_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            result = await provider.send_with_result("123456789", "t", "m", "critical")

        assert result.success is False
        assert "blocked" in result.error.lower()
        assert TELEGRAM_TOKEN not in result.error

    @pytest.mark.asyncio
    async def test_telegram_invalid_chat_mapping(self):
        provider = TelegramProvider(_telegram_config())
        response = MagicMock(
            status_code=400,
            text='{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}',
        )

        with patch(
            "app.services.notifications.telegram_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            result = await provider.send_with_result("123456789", "t", "m", "critical")

        assert result.success is False
        assert "chat" in result.error.lower()

    @pytest.mark.asyncio
    async def test_telegram_invalid_token_mapping(self):
        provider = TelegramProvider(_telegram_config())
        response = MagicMock(status_code=401, text="Unauthorized")

        with patch(
            "app.services.notifications.telegram_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            result = await provider.send_with_result("123456789", "t", "m", "critical")

        assert result.success is False
        assert "invalid or revoked" in result.error
        assert TELEGRAM_TOKEN not in result.error


class TestTelegramConnectionTokens:
    """Connection tokens must be secure, expiring and single-use."""

    def _record(self, used=False, expired=False):
        record = MagicMock()
        record.user_id = "user123"
        record.used = used
        record.is_expired = MagicMock(return_value=expired)
        record.save = AsyncMock()
        record.delete = AsyncMock()
        return record

    def test_connection_tokens_are_random_and_unpredictable(self):
        tokens = {generate_connection_token() for _ in range(50)}
        assert len(tokens) == 50
        for token in tokens:
            assert len(token) >= 24
            assert "user123" not in token  # no user information embedded

    def test_connection_token_storage_is_hashed(self):
        raw = generate_connection_token()
        hashed = hash_connection_token(raw)
        assert hashed != raw
        assert len(hashed) == 64  # sha256 hex digest

    @pytest.mark.asyncio
    async def test_connection_token_expiry(self):
        service = NotificationService()
        record = self._record(expired=True)

        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok:
            MockTok.find_one = AsyncMock(return_value=record)
            result = await service.complete_telegram_connect(
                "raw-token", "123456789", "testuser"
            )
        assert result["success"] is False
        assert "expired" in result["error"]
        record.delete.assert_awaited_once()

        # Status endpoint also reports expiry
        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok:
            MockTok.find_one = AsyncMock(return_value=record)
            status = await service.get_telegram_connect_status("user123", "raw-token")
        assert status["connected"] is False
        assert status.get("expired") is True

    @pytest.mark.asyncio
    async def test_connection_token_single_use(self):
        service = NotificationService()
        record = self._record(used=True)

        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok:
            MockTok.find_one = AsyncMock(return_value=record)
            result = await service.complete_telegram_connect(
                "raw-token", "123456789", "testuser"
            )
        assert result["success"] is False
        assert "already been used" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_token_invalid(self):
        service = NotificationService()
        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok:
            MockTok.find_one = AsyncMock(return_value=None)
            result = await service.complete_telegram_connect(
                "raw-token", "123456789", "testuser"
            )
        assert result["success"] is False
        assert "Invalid connection token" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_success_marks_used_and_creates_channel(self):
        service = NotificationService()
        record = self._record()

        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok, \
             patch("app.services.notification_service.NotificationChannelConfig") as MockCfg:
            MockTok.find_one = AsyncMock(return_value=record)
            MockCfg.find_one = AsyncMock(return_value=None)
            mock_insert = MockCfg.return_value.insert = AsyncMock()

            result = await service.complete_telegram_connect(
                "raw-token", "123456789", "testuser"
            )

        assert result["success"] is True
        assert result["user_id"] == "user123"
        assert record.used is True
        record.save.assert_awaited_once()
        mock_insert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_status_connected_after_use(self):
        service = NotificationService()
        record = self._record(used=True)
        record.chat_id = "123456789"
        record.telegram_username = "testuser"

        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok:
            MockTok.find_one = AsyncMock(return_value=record)
            status = await service.get_telegram_connect_status("user123", "raw-token")

        assert status["connected"] is True
        assert status["chat_id"] == "123456789"
        assert status["telegram_username"] == "testuser"

    @pytest.mark.asyncio
    async def test_connect_status_ownership_enforced(self):
        """Users can only poll the status of their own connection tokens."""
        service = NotificationService()
        record = self._record()
        record.user_id = "someone-else"

        with patch("app.services.notification_service.TelegramConnectionToken") as MockTok:
            MockTok.find_one = AsyncMock(return_value=record)
            status = await service.get_telegram_connect_status("user123", "raw-token")

        assert status["connected"] is False
        assert "Invalid" in status["error"]


# ---------------------------------------------------------------------------
# API integration tests (use the real app + MongoDB via the client fixture)
# ---------------------------------------------------------------------------


def _user_payload(prefix):
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"{prefix}_{uid}@test.com",
        "username": f"{prefix}{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }


async def _login_headers(client, payload):
    await client.post("/api/auth/register", json=payload)
    login = await client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_user_channel_ownership_api(client):
    """Users cannot read, update, delete or test another user's channels."""
    headers_a = await _login_headers(client, _user_payload("owna"))
    headers_b = await _login_headers(client, _user_payload("ownb"))

    resp = await client.post(
        "/api/notifications/settings/",
        headers=headers_a,
        json={
            "provider": "email",
            "enabled": True,
            "recipient": "owner@example.com",
            "min_severity": "warning",
            "notification_types": ["alert"],
            "cooldown_seconds": 300,
        },
    )
    assert resp.status_code == 200, resp.text
    channel = resp.json()
    channel_id = channel["id"]
    assert channel["user_id"] not in (None, "")

    # User B cannot see user A's channels
    list_b = await client.get("/api/notifications/settings/", headers=headers_b)
    assert list_b.status_code == 200
    assert all(c["id"] != channel_id for c in list_b.json())

    # User B cannot update, delete or test user A's channel
    resp = await client.put(
        f"/api/notifications/settings/{channel_id}",
        headers=headers_b,
        json={"enabled": False},
    )
    assert resp.status_code == 404

    resp = await client.delete(
        f"/api/notifications/settings/{channel_id}", headers=headers_b
    )
    assert resp.status_code == 404

    resp = await client.post(
        "/api/notifications/settings/test",
        headers=headers_b,
        json={"provider": "email", "channel_id": channel_id},
    )
    assert resp.status_code == 404

    # Owner can still see and manage their own channel
    list_a = await client.get("/api/notifications/settings/", headers=headers_a)
    assert any(c["id"] == channel_id for c in list_a.json())
    resp = await client.delete(
        f"/api/notifications/settings/{channel_id}", headers=headers_a
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_whatsapp_channel_validates_e164(client):
    """Invalid phone numbers are rejected; E.164 numbers are accepted."""
    headers = await _login_headers(client, _user_payload("badwa"))

    resp = await client.post(
        "/api/notifications/settings/",
        headers=headers,
        json={"provider": "whatsapp", "recipient": "12345"},
    )
    assert resp.status_code == 400
    assert "E.164" in resp.json()["message"]

    resp = await client.post(
        "/api/notifications/settings/",
        headers=headers,
        json={"provider": "whatsapp", "recipient": "+92 300 1234567"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recipient"] == "+92 300 1234567"
    # No platform credentials ever appear on a channel document/response
    assert WHATSAPP_TOKEN not in json.dumps(data)
    assert "access_token" not in json.dumps(data)

    # Email channel validation too
    resp = await client.post(
        "/api/notifications/settings/",
        headers=headers,
        json={"provider": "email", "recipient": "not-an-email"},
    )
    assert resp.status_code == 400

    # Cleanup
    await client.delete(f"/api/notifications/settings/{data['id']}", headers=headers)


@pytest.mark.asyncio
async def test_providers_status_endpoint_no_secrets(client):
    """GET /providers/status returns booleans only, never credentials."""
    headers = await _login_headers(client, _user_payload("pstat"))

    with patch.object(settings, "WHATSAPP_ACCESS_TOKEN", WHATSAPP_TOKEN), \
         patch.object(settings, "TELEGRAM_BOT_TOKEN", TELEGRAM_TOKEN), \
         patch.object(settings, "SMTP_PASSWORD", SMTP_PASSWORD):
        resp = await client.get("/api/notifications/settings/providers/status", headers=headers)

    assert resp.status_code == 200
    body = json.dumps(resp.json())
    assert WHATSAPP_TOKEN not in body
    assert TELEGRAM_TOKEN not in body
    assert SMTP_PASSWORD not in body
    providers = resp.json()["providers"]
    for provider in ("email", "whatsapp", "telegram"):
        assert "available" in providers[provider]
        assert "message" in providers[provider]


@pytest.mark.asyncio
async def test_telegram_webhook_completes_connection(client):
    """The public webhook maps /start <token> to the owning user's chat."""
    with patch(
        "app.routers.notification_settings_router.notification_service"
    ) as mock_service:
        mock_service.complete_telegram_connect = AsyncMock(
            return_value={"success": True, "user_id": "user123", "chat_id": "987654321"}
        )
        resp = await client.post(
            "/api/notifications/settings/telegram/webhook",
            json={
                "message": {
                    "text": "/start abc123token",
                    "chat": {"id": 987654321},
                    "from": {"username": "testuser"},
                }
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_service.complete_telegram_connect.assert_awaited_once_with(
        "abc123token", "987654321", "testuser"
    )


@pytest.mark.asyncio
async def test_telegram_webhook_rejects_bad_secret(client):
    """When a webhook secret is configured, mismatches are rejected."""
    with patch.object(settings, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"):
        resp = await client.post(
            "/api/notifications/settings/telegram/webhook",
            json={"message": {"text": "/start x", "chat": {"id": 1}}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_metrics_ingestion_200_when_notification_delivery_fails(client):
    """Metrics ingestion must still return 200 even if notification delivery fails."""
    headers = await _login_headers(client, _user_payload("metr"))
    server = (
        await client.post(
            "/api/servers/",
            headers=headers,
            json={"name": "NotifyFail", "ip_address": "10.9.9.9", "server_type": "web", "tags": []},
        )
    ).json()

    failing_channel = MagicMock(
        provider=NotificationProviderType.EMAIL,
        recipient="x@example.com",
        last_sent_at=None,
        cooldown_seconds=0,
        notification_types=["alert"],
        min_severity="info",
    )
    failing_channel.save = AsyncMock()

    # cpu 99 >= critical threshold (95) -> alert -> notification delivery explodes
    with patch("app.services.notification_service.NotificationChannelConfig") as MockCfg, \
         patch("app.services.notifications.EmailProvider") as MockEmail:
        MockCfg.find.return_value = MagicMock(
            to_list=AsyncMock(return_value=[failing_channel])
        )
        MockEmail.return_value.send_with_result = AsyncMock(
            side_effect=RuntimeError("SMTP down")
        )
        resp = await client.post(
            "/api/monitoring/metrics",
            json={
                "server_id": server["id"],
                "cpu_usage": 99.0,
                "memory_usage": 50.0,
                "disk_usage": 50.0,
            },
            headers={"X-Agent-Token": server["agent_token"]},
        )

    # Ingestion still succeeds despite the notification failure
    assert resp.status_code == 200

    # And the alert was still created
    alerts_resp = await client.get("/api/alerts", headers=headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    if isinstance(alerts, dict):
        alerts = alerts.get("items", [])
    assert any(a.get("server_id") == server["id"] for a in alerts)