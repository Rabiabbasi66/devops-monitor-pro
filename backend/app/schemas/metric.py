from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MetricIngest(BaseModel):
    server_id: str
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)
    memory_used: Optional[float] = None
    memory_available: Optional[float] = None
    disk_used: Optional[float] = None
    disk_available: Optional[float] = None
    network_received: float = 0.0
    network_sent: float = 0.0
    uptime: float = 0.0
    process_count: int = 0
    load_average: Optional[float] = None
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    response_time_ms: Optional[float] = None


class MetricResponse(BaseModel):
    id: str
    server_id: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    memory_used: Optional[float] = None
    memory_available: Optional[float] = None
    disk_used: Optional[float] = None
    disk_available: Optional[float] = None
    network_received: float
    network_sent: float
    uptime: float
    process_count: int
    load_average: Optional[float] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class MetricListResponse(BaseModel):
    items: List[MetricResponse]
    total: int
    limit: int
    hours: Optional[int] = None
