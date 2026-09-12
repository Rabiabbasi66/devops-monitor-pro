import enum
from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import Field


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class IncidentSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class Incident(Document):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    user_id: Indexed(str)
    severity: IncidentSeverity = IncidentSeverity.HIGH
    status: IncidentStatus = IncidentStatus.OPEN
    affected_servers: List[str] = Field(default_factory=list)
    related_alerts: List[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    duration_seconds: Optional[float] = None

    class Settings:
        name = "incidents"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("status", 1)],
            [("status", 1)],
            [("severity", 1)],
            [("created_at", -1)],
        ]