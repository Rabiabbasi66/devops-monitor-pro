"""
Email notification provider using SMTP.

Platform-managed: SMTP credentials come exclusively from environment
configuration (config.py). Users only configure their recipient address.
Credentials are never logged or included in error responses.
"""
import asyncio
import logging
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime

from .base import NotificationProvider, NotificationSendResult
from ...utils.secret_masking import redact_secrets
from ...utils.validators import validate_email_format

logger = logging.getLogger("devops_monitor")


class EmailProvider(NotificationProvider):
    """Email notification provider using SMTP."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = config.get("smtp_port", 587)
        self.smtp_username = config.get("smtp_username", "")
        self.smtp_password = config.get("smtp_password", "")
        self.smtp_use_tls = config.get("smtp_use_tls", True)
        self.smtp_from_email = config.get("smtp_from_email", self.smtp_username)
        self.smtp_from_name = config.get("smtp_from_name", "DevOps Monitor Pro")

    def missing_config(self) -> Optional[str]:
        """Platform SMTP configuration completeness check (no secrets).

        Evaluates configuration regardless of the enabled flag so the
        provider-status endpoint can report configured=false honestly.
        """
        if not self.smtp_server:
            return "Email provider is not configured (missing SMTP server)"
        if not (self.smtp_from_email or self.smtp_username):
            return "Email provider is not configured (missing sender address)"
        return None

    def validate_recipient(self, recipient: str) -> Optional[str]:
        base_error = super().validate_recipient(recipient)
        if base_error:
            return base_error
        if not validate_email_format(str(recipient).strip()):
            return "Invalid email address"
        return None

    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send email notification."""
        if not self.enabled:
            logger.debug("Email provider is disabled")
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
        """Send email and return a detailed (secret-free) result."""
        if not self.enabled:
            logger.debug("Email provider is disabled")
            return NotificationSendResult(False, "Email provider is not enabled")

        recipient_error = self.validate_recipient(recipient)
        if recipient_error:
            return NotificationSendResult(False, recipient_error)

        try:
            # Run SMTP operations in thread pool to avoid blocking async event loop
            return await asyncio.to_thread(
                self._send_sync,
                recipient,
                title,
                message,
                severity,
                metadata
            )
        except Exception as exc:
            # SMTP errors can embed server details; strip any credential values
            logger.error(
                "Failed to send email to %s: %s",
                recipient,
                redact_secrets(str(exc), [self.smtp_password]),
            )
            return NotificationSendResult(False, "Failed to send email")
    
    def _send_sync(
        self,
        recipient: str,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]]
    ) -> NotificationSendResult:
        """Synchronous SMTP send operation with mapped error causes."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{severity.upper()}] {title}"
            msg["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
            msg["To"] = recipient
            
            # Add HTML body
            html_body = self._create_html_body(title, message, severity, metadata)
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)
            
            # Add plain text body
            text_body = self._create_text_body(title, message, severity, metadata)
            text_part = MIMEText(text_body, "plain")
            msg.attach(text_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info("Email sent successfully to %s", recipient)
            return NotificationSendResult(True)

        except smtplib.SMTPAuthenticationError:
            # Never include credentials in the log or error response
            logger.error(
                "Email send failed: SMTP authentication rejected for account %s (credentials configured: %s)",
                self.smtp_username,
                bool(self.smtp_username and self.smtp_password),
            )
            return NotificationSendResult(False, "SMTP authentication failed (check platform SMTP settings)")
        except smtplib.SMTPConnectError as exc:
            logger.error("Email send failed: could not connect to SMTP server: %s", redact_secrets(str(exc), [self.smtp_password]))
            return NotificationSendResult(False, "Could not connect to SMTP server")
        except smtplib.SMTPServerDisconnected as exc:
            logger.error("Email send failed: SMTP server disconnected: %s", redact_secrets(str(exc), [self.smtp_password]))
            return NotificationSendResult(False, "SMTP server disconnected unexpectedly")
        except smtplib.SMTPException as exc:
            logger.error("Email send failed: SMTP error: %s", redact_secrets(str(exc), [self.smtp_password]))
            return NotificationSendResult(False, "SMTP server rejected the message")
        except (socket.timeout, TimeoutError):
            logger.error("Email send failed: SMTP connection to %s:%s timed out", self.smtp_server, self.smtp_port)
            return NotificationSendResult(False, "SMTP connection timed out")
        except OSError as exc:
            logger.error("Email send failed: connection error: %s", redact_secrets(str(exc), [self.smtp_password]))
            return NotificationSendResult(False, "Could not reach SMTP server")
    
    async def send_test(self, recipient: str) -> bool:
        """Send test email."""
        return await self.send(
            recipient=recipient,
            title="Test Notification",
            message="This is a test notification from DevOps Monitor Pro. Your email configuration is working correctly.",
            severity="info",
            metadata={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
    
    def _create_html_body(
        self,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """Create HTML email body."""
        severity_colors = {
            "info": "#0066cc",
            "warning": "#ff9900",
            "high": "#ff6600",
            "critical": "#cc0000"
        }
        color = severity_colors.get(severity.lower(), "#666666")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 0 0 5px 5px; }}
                .severity {{ text-transform: uppercase; font-weight: bold; }}
                .metadata {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">DevOps Monitor Pro</h1>
                    <div class="severity">{severity} Alert</div>
                </div>
                <div class="content">
                    <h2 style="margin-top: 0;">{title}</h2>
                    <p>{message}</p>
                </div>
        """
        
        if metadata:
            html += f'<div class="metadata"><strong>Details:</strong><br>'
            for key, value in metadata.items():
                if key != "test":  # Don't show test flag
                    html += f"{key}: {value}<br>"
            html += f'<br><em>Sent: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</em></div>'
        
        html += """
            </div>
        </body>
        </html>
        """
        return html
    
    def _create_text_body(
        self,
        title: str,
        message: str,
        severity: str,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """Create plain text email body."""
        text = f"""
DevOps Monitor Pro - {severity.upper()} Alert
{'=' * 50}

{title}

{message}
"""
        
        if metadata:
            text += "\n\nDetails:\n"
            for key, value in metadata.items():
                if key != "test":
                    text += f"{key}: {value}\n"
            text += f"\nSent: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return text