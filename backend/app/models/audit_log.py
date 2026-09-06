import enum
from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    SERVER_CREATED = "server_created"
    SERVER_UPDATED = "server_updated"
    SERVER_DELETED = "server_deleted"
    STATUS_CHANGED = "status_changed"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RESOLVED = "alert_resolved"
    ALERT_REOPENED = "alert_reopened"
    THRESHOLD_CHANGED = "threshold_changed"


class AuditLog(Document):
    user_id: Indexed(str)
    action: AuditAction
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "audit_logs"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("timestamp", -1)],
            [("action", 1)],
            [("timestamp", -1)],
        ]
