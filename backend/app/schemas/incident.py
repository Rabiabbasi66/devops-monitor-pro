from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..models.incident import IncidentStatus, IncidentSeverity


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    severity: IncidentSeverity = IncidentSeverity.HIGH
    affected_servers: List[str] = Field(default_factory=list)
    related_alerts: List[str] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = None
    affected_servers: Optional[List[str]] = None
    related_alerts: Optional[List[str]] = None


class IncidentResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    user_id: str
    severity: IncidentSeverity
    status: IncidentStatus
    affected_servers: List[str]
    related_alerts: List[str]
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True