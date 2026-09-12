from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..models.incident import IncidentStatus, IncidentSeverity
from ..models.user import User
from ..schemas.incident import IncidentCreate, IncidentResponse, IncidentUpdate
from ..services.incident_service import IncidentService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/incidents", tags=["Incidents"])
incident_service = IncidentService()


def _serialize_incident(incident) -> IncidentResponse:
    return IncidentResponse(
        id=str(incident.id),
        title=incident.title,
        description=incident.description,
        user_id=incident.user_id,
        severity=incident.severity,
        status=incident.status,
        affected_servers=incident.affected_servers,
        related_alerts=incident.related_alerts,
        assigned_to=incident.assigned_to,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        acknowledged_at=incident.acknowledged_at,
        acknowledged_by=incident.acknowledged_by,
        resolved_at=incident.resolved_at,
        resolved_by=incident.resolved_by,
        duration_seconds=incident.duration_seconds,
    )


@router.post("/", response_model=IncidentResponse, summary="Create incident")
async def create_incident(
    incident_data: IncidentCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.create_incident(
        incident_data, current_user, ip=request.client.host if request.client else None
    )
    return _serialize_incident(incident)


@router.get("/", response_model=List[IncidentResponse], summary="List incidents")
async def list_incidents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    status: Optional[IncidentStatus] = None,
    severity: Optional[IncidentSeverity] = None,
    current_user: User = Depends(get_current_active_user),
):
    incidents = await incident_service.list_incidents(
        current_user, skip=skip, limit=limit, status=status, severity=severity
    )
    return [_serialize_incident(i) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse, summary="Get incident")
async def get_incident(
    incident_id: str,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.get_incident(incident_id, current_user)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(incident)


@router.put("/{incident_id}", response_model=IncidentResponse, summary="Update incident")
async def update_incident(
    incident_id: str,
    update_data: IncidentUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.update_incident(
        incident_id, update_data, current_user, ip=request.client.host if request.client else None
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(incident)


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse, summary="Acknowledge incident")
async def acknowledge_incident(
    incident_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.acknowledge_incident(
        incident_id, current_user, ip=request.client.host if request.client else None
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(incident)


@router.post("/{incident_id}/resolve", response_model=IncidentResponse, summary="Resolve incident")
async def resolve_incident(
    incident_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.resolve_incident(
        incident_id, current_user, ip=request.client.host if request.client else None
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(incident)


@router.post("/{incident_id}/reopen", response_model=IncidentResponse, summary="Reopen incident")
async def reopen_incident(
    incident_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.reopen_incident(
        incident_id, current_user, ip=request.client.host if request.client else None
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(incident)


@router.delete("/{incident_id}", summary="Delete incident")
async def delete_incident(
    incident_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    success = await incident_service.delete_incident(
        incident_id, current_user, ip=request.client.host if request.client else None
    )
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"success": True, "message": "Incident deleted successfully"}


@router.post("/{incident_id}/alerts/{alert_id}", response_model=IncidentResponse, summary="Link alert to incident")
async def link_alert_to_incident(
    incident_id: str,
    alert_id: str,
    current_user: User = Depends(get_current_active_user),
):
    incident = await incident_service.link_alert_to_incident(incident_id, alert_id, current_user)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(incident)
