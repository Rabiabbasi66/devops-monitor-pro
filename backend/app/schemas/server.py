from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

from ..models.server import ServerStatus, HealthStatus, ServerThreshold


class ServerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    ip_address: str
    server_type: str
    tags: List[str] = []

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        parts = value.split(".")
        if len(parts) != 4:
            raise ValueError("Invalid IP address format")
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                raise ValueError("Invalid IP address")
        return value


class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    server_type: Optional[str] = None
    tags: Optional[List[str]] = None


class ServerStatusUpdate(BaseModel):
    status: ServerStatus
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)


class ThresholdUpdate(BaseModel):
    thresholds: ServerThreshold


class ServerResponse(BaseModel):
    id: str
    name: str
    ip_address: str
    server_type: str
    status: ServerStatus
    health_status: HealthStatus
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: float
    response_time_ms: Optional[float] = None
    last_checked: datetime
    last_seen: Optional[datetime] = None
    tags: List[str]
    user_id: str
    agent_token: Optional[str] = None
    thresholds: ServerThreshold
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
