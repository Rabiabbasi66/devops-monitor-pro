import enum
from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import Field


class AlertRuleOperator(str, enum.Enum):
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="


class AlertRuleMetricType(str, enum.Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK_SENT = "network_sent"
    NETWORK_RECEIVED = "network_received"
    LOAD_AVERAGE = "load_average"
    PROCESS_CPU = "process_cpu"
    PROCESS_MEMORY = "process_memory"


class AlertRule(Document):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    user_id: Indexed(str)
    server_id: Optional[Indexed(str)] = None  # null = global rule
    metric_type: AlertRuleMetricType
    operator: AlertRuleOperator = AlertRuleOperator.GREATER_THAN
    warning_threshold: float
    critical_threshold: float
    evaluation_interval_seconds: int = Field(default=60)
    cooldown_seconds: int = Field(default=300)
    enabled: bool = True
    severity: str = Field(default="high")  # info, warning, high, critical
    notification_channels: List[str] = Field(default_factory=lambda: ["in_app"])
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "alert_rules"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("enabled", 1)],
            [("server_id", 1), ("enabled", 1)],
            [("metric_type", 1)],
        ]