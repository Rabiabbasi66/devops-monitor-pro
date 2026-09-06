from fastapi import APIRouter, Depends, Query

from ..models.audit_log import AuditLog
from ..models.user import User
from ..schemas.audit import AuditLogListResponse, AuditLogResponse
from ..utils.security import get_current_admin_user

router = APIRouter(prefix="/audit-logs", tags=["Admin"])


@router.get("", response_model=AuditLogListResponse, summary="List audit logs (admin)")
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_admin_user),
):
    logs = await AuditLog.find().sort(-AuditLog.timestamp).skip(skip).limit(limit).to_list()
    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=str(log.id),
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                timestamp=log.timestamp,
            )
            for log in logs
        ],
        total=len(logs),
    )
