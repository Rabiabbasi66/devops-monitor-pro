from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import Field


class Metric(Document):
    server_id: Indexed(str)
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    memory_used: Optional[float] = None
    memory_available: Optional[float] = None
    disk_used: Optional[float] = None
    disk_available: Optional[float] = None
    network_received: float = 0.0
    network_sent: float = 0.0
    uptime: float = 0.0
    process_count: int = 0
    load_average: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "metrics"
        use_state_management = True
        indexes = [
            [("server_id", 1), ("timestamp", -1)],
            [("timestamp", 1)],
        ]
