from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..models.alert import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    server_id: str
    server_name: str
    message: str
    severity: AlertSeverity
    metric_type: str
    current_value: float
    threshold: float


class AlertResponse(BaseModel):
    id: str
    server_id: str
    server_name: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    metric_type: str
    current_value: float
    threshold: float
    resolved: bool
    occurrence_count: int = 1
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    duration_seconds: Optional[float] = None
    first_occurred_at: Optional[datetime] = None
    last_occurred_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
