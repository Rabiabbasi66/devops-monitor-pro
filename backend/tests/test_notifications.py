"""
Unit tests for notification providers and notification service.
Note: Integration tests requiring MongoDB are skipped due to pre-existing test infrastructure issues.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notifications.base import NotificationProvider, NotificationChannel
from app.services.notifications.email_provider import EmailProvider
from app.services.notification_service import NotificationService
from app.models.notification_settings import NotificationProviderType
from app.models.email_verification import EmailVerification


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
        assert hasattr(service, 'request_email_verification')
        assert hasattr(service, 'verify_email_code')


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
from app.services.notifications.base import NotificationSendResult  # noqa: E402

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


class TestMissingProviderConfiguration:
    """Missing platform credentials must produce useful, secret-free errors."""

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
        with patch.object(settings, "SMTP_ENABLED", True), \
             patch.object(settings, "SMTP_PASSWORD", SMTP_PASSWORD), \
             patch("app.services.notifications.EmailProvider") as MockEmail:
            instance = MockEmail.return_value
            instance.is_enabled.return_value = True
            instance.missing_config.return_value = None
            instance.validate_recipient.return_value = None
            instance.send_with_result = AsyncMock(
                return_value=NotificationSendResult(False, "SMTP authentication failed")
            )

            result = await service.send_test_notification(
                user_id="user123",
                provider=NotificationProviderType.EMAIL,
                recipient="client@example.com",
            )

        assert result["success"] is False
        assert result["error"] == "SMTP authentication failed"
        assert SMTP_PASSWORD not in json.dumps(result)


class TestEmailVerification:
    """Email verification flow tests."""

    @pytest.mark.asyncio
    async def test_request_verification_invalid_email(self):
        service = NotificationService()
        result = await service.request_email_verification("user123", "invalid-email")
        assert result["success"] is False
        assert "Invalid email address" in result["error"]

    @pytest.mark.asyncio
    async def test_request_verification_smtp_not_configured(self):
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", False):
            result = await service.request_email_verification("user123", "test@example.com")
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_verify_invalid_code_format(self):
        service = NotificationService()
        result = await service.verify_email_code("user123", "test@example.com", "abc")
        assert result["success"] is False
        assert "Invalid verification code format" in result["error"]

    @pytest.mark.asyncio
    async def test_verify_wrong_code(self):
        service = NotificationService()
        # Mock the database operations since MongoDB is not available
        with patch.object(EmailVerification, "find_one", AsyncMock(return_value=None)):
            result = await service.verify_email_code("user123", "test@example.com", "123456")
        assert result["success"] is False
        assert "Invalid verification code" in result["error"]

    @pytest.mark.asyncio
    async def test_request_verification_smtp_enabled_invokes_provider_instance(self):
        """SMTP-enabled request path must send via a real provider INSTANCE.

        Regression test: request_email_verification() used to call
        send_with_result() on the provider CLASS (self._providers maps type ->
        class), which raised TypeError (HTTP 500) on every request once SMTP
        was enabled. The mock provider makes that regression deterministic:
        success is only possible if the service awaited send_with_result() on
        the instance it constructed, and find(...).delete_many()/insert() are
        mocked so no MongoDB connection is required.
        """
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", True), \
             patch("app.services.notification_service.generate_verification_code", return_value="654321"), \
             patch("app.services.notifications.EmailProvider") as MockEmail, \
             patch("app.services.notification_service.EmailVerification") as MockEV:
            MockEV.find.return_value.delete_many = AsyncMock()
            record = MockEV.return_value
            record.insert = AsyncMock()
            instance = MockEmail.return_value
            instance.is_enabled.return_value = True
            instance.missing_config.return_value = None
            instance.send_with_result = AsyncMock(return_value=NotificationSendResult(True))

            result = await service.request_email_verification(
                "user123", "client@example.com"
            )

        # The provider instance was actually invoked and reported success.
        instance.send_with_result.assert_awaited_once()
        assert instance.send_with_result.await_args.kwargs["recipient"] == "client@example.com"
        assert instance.send_with_result.await_args.kwargs["message"].startswith(
            "Your verification code is:"
        )
        assert result["success"] is True
        assert result["message"] == "Verification code sent to your email"
        # The raw code ("654321") must never leak into the API response.
        assert "654321" not in json.dumps(result)
        # The verification record was persisted with a hash (never the raw code).
        record.insert.assert_awaited_once()
        assert MockEV.call_args.kwargs["user_id"] == "user123"
        assert MockEV.call_args.kwargs["email"] == "client@example.com"
        code_hash = MockEV.call_args.kwargs["code_hash"]
        assert code_hash and len(code_hash) == 64  # sha256 hex digest
        assert code_hash != "654321"

    @pytest.mark.asyncio
    async def test_request_verification_provider_failure_returns_failure(self):
        """Provider failure must return failure (record cleaned up), never fake success."""
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", True), \
             patch("app.services.notifications.EmailProvider") as MockEmail, \
             patch("app.services.notification_service.EmailVerification") as MockEV:
            MockEV.find.return_value.delete_many = AsyncMock()
            record = MockEV.return_value
            record.insert = AsyncMock()
            record.delete = AsyncMock()
            instance = MockEmail.return_value
            instance.is_enabled.return_value = True
            instance.missing_config.return_value = None
            instance.send_with_result = AsyncMock(
                return_value=NotificationSendResult(False, "SMTP connection refused")
            )

            result = await service.request_email_verification(
                "user123", "client@example.com"
            )

        instance.send_with_result.assert_awaited_once()
        assert result["success"] is False
        assert result["error"] == "SMTP connection refused"
        # Failed send must clean up the verification record (no orphan codes).
        record.delete.assert_awaited_once()


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
             patch.object(settings, "SMTP_FROM_EMAIL", "platform@example.com"):
            status = service.get_provider_status()

        serialized = json.dumps(status)
        assert status["email"]["available"] is True
        assert SMTP_PASSWORD not in serialized

    @pytest.mark.asyncio
    async def test_provider_status_reports_unavailable_without_secrets(self):
        service = NotificationService()
        with patch.object(settings, "SMTP_ENABLED", False), \
             patch.object(settings, "SMTP_PASSWORD", SMTP_PASSWORD):
            status = service.get_provider_status()

        assert status["email"]["available"] is False
        assert "unavailable" in status["email"]["message"].lower()
        assert SMTP_PASSWORD not in json.dumps(status)

    def test_channel_metadata_never_stores_secrets(self):
        sanitized = sanitize_provider_metadata(
            {
                "chat_id": "123456789",
                "telegram_username": "testuser",
                "access_token": "EAAB-super-secret-token-xyz",
                "bot_token": "123456:ABC-super-secret-bot-token",
                "smtp_password": "super-secret-smtp-password",
                "api_key": "key123",
            }
        )
        assert sanitized == {"chat_id": "123456789", "telegram_username": "testuser"}


class TestSecretSafetyLogs:
    """Provider credentials must never appear in log output."""

    @pytest.mark.asyncio
    async def test_smtp_password_never_logged(self, caplog):
        provider = EmailProvider(_email_config())
        caplog.set_level(logging.ERROR, logger="devops_monitor")

        with patch(
            "app.services.notifications.email_provider.smtplib.SMTP"
        ) as mock_smtp:
            mock_smtp.return_value.__enter__.side_effect = Exception(
                f"Authentication failed for {SMTP_PASSWORD}"
            )
            result = await provider.send_with_result("a@example.com", "t", "m", "critical")

        assert result.success is False
        assert SMTP_PASSWORD not in caplog.text
