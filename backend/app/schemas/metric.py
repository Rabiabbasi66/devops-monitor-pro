from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class MetricIngest(BaseModel):
    """Schema for metrics ingested from the monitoring agent."""

    model_config = {"extra": "ignore"}  # silently ignore unknown fields (e.g. process_count from old agents)

    server_id: str
    agent_version: Optional[str] = None
    cpu_usage: float = Field(..., ge=0, le=100)
    cpu_count: Optional[int] = None
    cpu_physical: Optional[int] = None
    cpu_frequency: Optional[float] = None
    cpu_per_core: Optional[List[float]] = None
    memory_usage: float = Field(..., ge=0, le=100)
    memory_used: Optional[float] = None
    memory_available: Optional[float] = None
    memory_total: Optional[float] = None
    memory_free: Optional[float] = None
    swap_total: Optional[float] = None
    swap_used: Optional[float] = None
    swap_percent: Optional[float] = None
    disk_usage: float = Field(..., ge=0, le=100)
    disk_used: Optional[float] = None
    disk_available: Optional[float] = None
    disk_total: Optional[float] = None
    disk_read_bytes: Optional[float] = None
    disk_write_bytes: Optional[float] = None
    disk_read_count: Optional[int] = None
    disk_write_count: Optional[int] = None
    network_sent: float = 0.0
    network_received: float = 0.0
    packets_sent: Optional[int] = None
    packets_received: Optional[int] = None
    errors_in: Optional[int] = None
    errors_out: Optional[int] = None
    dropped_in: Optional[int] = None
    dropped_out: Optional[int] = None
    network_interfaces: Optional[Dict[str, Any]] = None
    uptime: float = 0.0
    load_average: Optional[float] = None
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    platform: Optional[str] = None
    python_version: Optional[str] = None
    boot_time: Optional[float] = None
    processes: Optional[Dict[str, Any]] = None
    response_time_ms: Optional[float] = None


class MetricResponse(BaseModel):
    id: str
    server_id: str
    cpu_usage: float
    cpu_count: Optional[int] = None
    cpu_physical: Optional[int] = None
    cpu_frequency: Optional[float] = None
    cpu_per_core: Optional[List[float]] = None
    memory_usage: float
    memory_used: Optional[float] = None
    memory_available: Optional[float] = None
    memory_total: Optional[float] = None
    memory_free: Optional[float] = None
    swap_total: Optional[float] = None
    swap_used: Optional[float] = None
    swap_percent: Optional[float] = None
    disk_usage: float
    disk_used: Optional[float] = None
    disk_available: Optional[float] = None
    disk_total: Optional[float] = None
    disk_read_bytes: Optional[float] = None
    disk_write_bytes: Optional[float] = None
    disk_read_count: Optional[int] = None
    disk_write_count: Optional[int] = None
    network_sent: float
    network_received: float
    packets_sent: Optional[int] = None
    packets_received: Optional[int] = None
    errors_in: Optional[int] = None
    errors_out: Optional[int] = None
    dropped_in: Optional[int] = None
    dropped_out: Optional[int] = None
    network_interfaces: Optional[Dict[str, Any]] = None
    uptime: float
    load_average: Optional[float] = None
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    platform: Optional[str] = None
    python_version: Optional[str] = None
    boot_time: Optional[float] = None
    processes: Optional[Dict[str, Any]] = None
    response_time_ms: Optional[float] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class MetricListResponse(BaseModel):
    items: List[MetricResponse]
    total: int
    limit: int
    hours: Optional[int] = None
