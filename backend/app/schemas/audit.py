from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..models.audit_log import AuditAction


class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    action: AuditAction
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
