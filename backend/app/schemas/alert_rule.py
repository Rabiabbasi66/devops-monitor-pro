from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..models.alert_rule import AlertRuleOperator, AlertRuleMetricType


class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    server_id: Optional[str] = None
    metric_type: AlertRuleMetricType
    operator: AlertRuleOperator = AlertRuleOperator.GREATER_THAN
    warning_threshold: float
    critical_threshold: float
    evaluation_interval_seconds: int = Field(default=60, ge=10)
    cooldown_seconds: int = Field(default=300, ge=0)
    enabled: bool = True
    severity: str = Field(default="high")
    notification_channels: List[str] = Field(default_factory=lambda: ["in_app"])


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    server_id: Optional[str] = None
    metric_type: Optional[AlertRuleMetricType] = None
    operator: Optional[AlertRuleOperator] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    evaluation_interval_seconds: Optional[int] = Field(None, ge=10)
    cooldown_seconds: Optional[int] = Field(None, ge=0)
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    notification_channels: Optional[List[str]] = None


class AlertRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    user_id: str
    server_id: Optional[str] = None
    metric_type: AlertRuleMetricType
    operator: AlertRuleOperator
    warning_threshold: float
    critical_threshold: float
    evaluation_interval_seconds: int
    cooldown_seconds: int
    enabled: bool
    severity: str
    notification_channels: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True