import enum
from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class ServerStatus(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


class HealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ServerThreshold(BaseModel):
    cpu_warning: float = 80.0
    cpu_critical: float = 95.0
    memory_warning: float = 85.0
    memory_critical: float = 95.0
    disk_warning: float = 85.0
    disk_critical: float = 90.0


class Server(Document):
    name: str = Field(..., min_length=2, max_length=50)
    ip_address: str
    server_type: str = Field(..., description="e.g., web, db, api")
    status: ServerStatus = ServerStatus.UNKNOWN
    health_status: HealthStatus = HealthStatus.UNKNOWN
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    platform: Optional[str] = None
    cpu_usage: float = Field(default=0.0, ge=0, le=100)
    memory_usage: float = Field(default=0.0, ge=0, le=100)
    disk_usage: float = Field(default=0.0, ge=0, le=100)
    uptime: float = 0.0
    response_time_ms: Optional[float] = None
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None
    agent_version: Optional[str] = None
    agent_status: str = "unknown"  # enrolled, active, stale, offline, revoked
    tags: List[str] = Field(default_factory=list)
    environment: Optional[str] = None  # Production, Staging, Development, Testing
    description: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[str] = None
    monitoring_enabled: bool = True
    user_id: Indexed(str)
    agent_token: Optional[str] = None
    thresholds: ServerThreshold = Field(default_factory=ServerThreshold)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "servers"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("status", 1)],
            [("user_id", 1)],
            [("status", 1)],
            [("health_status", 1)],
            [("agent_token", 1)],
            [("environment", 1)],
            [("tags", 1)],
        ]
