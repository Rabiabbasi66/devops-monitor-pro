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
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
