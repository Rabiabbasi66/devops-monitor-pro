import enum
from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(Document):
    server_id: Indexed(str)
    server_name: str
    message: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.PENDING
    metric_type: str
    current_value: float
    threshold: float
    resolved: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    duration_seconds: Optional[float] = None
    occurrence_count: int = 1
    first_occurred_at: datetime = Field(default_factory=datetime.utcnow)
    last_occurred_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "alerts"
        use_state_management = True
        indexes = [
            [("server_id", 1), ("resolved", 1)],
            [("server_id", 1), ("metric_type", 1), ("status", 1)],
            [("severity", 1)],
            [("created_at", -1)],
            [("first_occurred_at", -1)],
        ]
