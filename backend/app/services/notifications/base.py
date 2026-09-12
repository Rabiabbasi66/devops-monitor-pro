"""
Base notification provider interface.
All notification providers should inherit from this base class.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("devops_monitor")


class NotificationSendResult:
    """Detailed result of a provider send attempt.

    ``error`` messages are static, human-readable strings and must NEVER
    contain provider credentials (tokens, passwords, etc.).
    """

    def __init__(self, success: bool, error: Optional[str] = None):
        self.success = success
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"NotificationSendResult(success={self.success}, error={self.error!r})"


class NotificationProvider(ABC):
    """Base class for notification providers."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.name = self.__class__.__name__

    def missing_config(self) -> Optional[str]:
        """Return a human-readable message when required platform provider
        configuration is missing, or None when the provider is fully
        configured. Messages never include secret values.

        Concrete providers override this method.
        """
        return None

    def validate_recipient(self, recipient: str) -> Optional[str]:
        """Return an error message when the recipient is invalid for this
        provider, or None when it is valid.

        Concrete providers override this method.
        """
        if not recipient or not str(recipient).strip():
            return "Recipient is required"
        return None
    
    @abstractmethod
    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a notification.
        
        Args:
            recipient: Recipient identifier (email, phone, chat_id, etc.)
            title: Notification title
            message: Notification message
            severity: Alert severity (info, warning, high, critical)
            metadata: Additional metadata for the notification
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass

    async def send_with_result(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NotificationSendResult:
        """Send a notification and return a detailed result.

        Default implementation wraps ``send()``; concrete providers override
        this to surface specific error causes (auth failure, timeout, etc.).
        """
        try:
            success = await self.send(recipient, title, message, severity, metadata)
            return NotificationSendResult(success=success)
        except Exception:
            # Providers normally handle their own errors; this is a last resort
            logger.exception("Provider %s raised unexpectedly", self.name)
            return NotificationSendResult(success=False, error="Internal provider error")
    
    @abstractmethod
    async def send_test(self, recipient: str) -> bool:
        """
        Send a test notification to verify configuration.
        
        Args:
            recipient: Recipient identifier
            
        Returns:
            bool: True if test notification was sent successfully
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if this provider is enabled."""
        return self.enabled
    
    def should_send_for_severity(self, severity: str, min_severity: str) -> bool:
        """
        Check if notification should be sent based on severity.
        
        Args:
            severity: Current alert severity
            min_severity: Minimum severity threshold
            
        Returns:
            bool: True if notification should be sent
        """
        severity_order = {
            "info": 0,
            "warning": 1,
            "high": 2,
            "critical": 3
        }
        
        try:
            current_level = severity_order.get(severity.lower(), 0)
            min_level = severity_order.get(min_severity.lower(), 0)
            return current_level >= min_level
        except Exception:
            logger.error(f"Invalid severity comparison: {severity} vs {min_severity}")
            return False


class NotificationChannel:
    """Represents a notification channel configuration."""
    
    def __init__(
        self,
        provider: str,
        enabled: bool,
        recipient: str,
        min_severity: str = "warning",
        notification_types: Optional[list] = None
    ):
        self.provider = provider
        self.enabled = enabled
        self.recipient = recipient
        self.min_severity = min_severity
        self.notification_types = notification_types or [
            "alert", "recovery", "offline", "security"
        ]
    
    def should_send(self, notification_type: str, severity: str) -> bool:
        """
        Check if notification should be sent through this channel.
        
        Args:
            notification_type: Type of notification (alert, recovery, etc.)
            severity: Alert severity
            
        Returns:
            bool: True if notification should be sent
        """
        if not self.enabled:
            return False
        
        if notification_type not in self.notification_types:
            return False
        
        severity_order = {
            "info": 0,
            "warning": 1,
            "high": 2,
            "critical": 3
        }
        
        try:
            current_level = severity_order.get(severity.lower(), 0)
            min_level = severity_order.get(self.min_severity.lower(), 0)
            return current_level >= min_level
        except Exception:
            logger.error(f"Invalid severity comparison: {severity} vs {self.min_severity}")
            return False