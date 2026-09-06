from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..models.alert import AlertStatus
from ..models.user import User
from ..schemas.alert import AlertListResponse, AlertResponse
from ..services.alert_service import AlertService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])
alert_service = AlertService()


def _alert_response(alert) -> AlertResponse:
    return AlertResponse(
        id=str(alert.id),
        server_id=alert.server_id,
        server_name=alert.server_name,
        message=alert.message,
        severity=alert.severity,
        status=alert.status,
        metric_type=alert.metric_type,
        current_value=alert.current_value,
        threshold=alert.threshold,
        resolved=alert.resolved,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        created_at=alert.created_at,
    )


@router.get("", response_model=AlertListResponse, summary="List alerts")
async def list_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
):
    alerts = await alert_service.list_alerts(current_user, skip=skip, limit=limit)
    items = [_alert_response(a) for a in alerts]
    return AlertListResponse(items=items, total=len(items))


@router.get("/pending", response_model=AlertListResponse, summary="List pending alerts")
async def list_pending_alerts(
    current_user: User = Depends(get_current_active_user),
):
    alerts = await alert_service.list_alerts(current_user, pending_only=True)
    items = [_alert_response(a) for a in alerts]
    return AlertListResponse(items=items, total=len(items))


@router.get("/{alert_id}", response_model=AlertResponse, summary="Get alert")
async def get_alert(
    alert_id: str,
    current_user: User = Depends(get_current_active_user),
):
    alert = await alert_service.get_alert_for_user(alert_id, current_user)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_response(alert)


@router.put("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    alert = await alert_service.get_alert_for_user(alert_id, current_user)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Alert already resolved")
    updated = await alert_service.acknowledge(
        alert, current_user, ip=request.client.host if request.client else None
    )
    return _alert_response(updated)


@router.put("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert_endpoint(
    alert_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    alert = await alert_service.get_alert_for_user(alert_id, current_user)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    updated = await alert_service.resolve(
        alert, current_user, ip=request.client.host if request.client else None
    )
    return _alert_response(updated)


@router.put("/{alert_id}/reopen", response_model=AlertResponse)
async def reopen_alert_endpoint(
    alert_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    alert = await alert_service.get_alert_for_user(alert_id, current_user)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    updated = await alert_service.reopen(
        alert, current_user, ip=request.client.host if request.client else None
    )
    return _alert_response(updated)
