from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..models.user import User
from ..schemas.server import (
    ServerCreate,
    ServerResponse,
    ServerStatusUpdate,
    ServerUpdate,
    ThresholdUpdate,
)
from ..services.alert_service import AlertService
from ..services.monitoring_service import MonitoringService
from ..services.server_service import ServerService, serialize_server
from ..repositories.metric_repository import MetricRepository
from ..schemas.metric import MetricIngest
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/servers", tags=["Servers"])

server_service = ServerService()
metric_repo = MetricRepository()
alert_service = AlertService()
monitoring_service = MonitoringService()


@router.post("/", response_model=ServerResponse, summary="Create a server")
async def create_new_server(
    server_data: ServerCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.create(
        server_data, current_user, ip=request.client.host if request.client else None
    )
    return serialize_server(server, include_token=True)


@router.get("/", response_model=List[ServerResponse], summary="List servers")
async def list_servers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    servers = await server_service.list_servers(current_user, skip, limit, status)
    return [serialize_server(s) for s in servers]


@router.get("/alerts/pending", include_in_schema=False)
async def legacy_pending_alerts(current_user: User = Depends(get_current_active_user)):
    from .alerts_router import list_pending_alerts

    return await list_pending_alerts(current_user=current_user)


@router.get("/analytics/dashboard", include_in_schema=False)
async def legacy_dashboard(current_user: User = Depends(get_current_active_user)):
    from .dashboard_router import get_summary

    return await get_summary(current_user=current_user)


@router.get("/{server_id}", response_model=ServerResponse, summary="Get server")
async def get_server(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return serialize_server(server, include_token=False)


@router.put("/{server_id}", response_model=ServerResponse, summary="Update server")
async def update_server_details(
    server_id: str,
    update_data: ServerUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    updated = await server_service.update_server(
        server, update_data, current_user, ip=request.client.host if request.client else None
    )
    return serialize_server(updated)


@router.put("/{server_id}/status", response_model=ServerResponse, summary="Update status")
async def update_status(
    server_id: str,
    status_update: ServerStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    updated = await server_service.update_status(
        server, status_update, current_user, ip=request.client.host if request.client else None
    )

    metric = await metric_repo.create(
        MetricIngest(
            server_id=server_id,
            cpu_usage=status_update.cpu_usage,
            memory_usage=status_update.memory_usage,
            disk_usage=status_update.disk_usage,
        )
    )
    await alert_service.evaluate_metrics(updated)

    from ..services.websocket_manager import ws_manager

    await ws_manager.broadcast(
        server_id,
        {
            "type": "metric",
            "server_id": server_id,
            "cpu_usage": updated.cpu_usage,
            "memory_usage": updated.memory_usage,
            "disk_usage": updated.disk_usage,
            "status": updated.status.value,
            "health_status": updated.health_status.value,
            "timestamp": metric.timestamp.isoformat(),
        },
    )

    return serialize_server(updated)


@router.put("/{server_id}/thresholds", response_model=ServerResponse)
async def update_thresholds(
    server_id: str,
    body: ThresholdUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    updated = await server_service.update_thresholds(
        server, body.thresholds, current_user, ip=request.client.host if request.client else None
    )
    return serialize_server(updated)


@router.put("/alerts/{alert_id}/resolve", include_in_schema=False)
async def legacy_resolve_alert(
    alert_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    from .alerts_router import resolve_alert_endpoint

    return await resolve_alert_endpoint(alert_id, request, current_user)


@router.delete("/{server_id}", summary="Delete server")
async def delete_server_endpoint(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    await server_service.delete_server(
        server, current_user, ip=request.client.host if request.client else None
    )
    return {"success": True, "message": "Server deleted successfully"}
