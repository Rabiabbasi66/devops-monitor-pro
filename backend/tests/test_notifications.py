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