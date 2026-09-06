"""
Email notification provider using SMTP.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime

from .base import NotificationProvider

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
            
            logger.info(f"Email sent successfully to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False
    
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