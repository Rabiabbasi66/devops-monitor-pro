from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models.user import User
from ..repositories.metric_repository import MetricRepository
from ..schemas.metric import MetricListResponse, MetricResponse
from ..services.server_service import ServerService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/servers", tags=["Metrics"])
metric_repo = MetricRepository()
server_service = ServerService()


def _metric_response(metric) -> MetricResponse:
    return MetricResponse(
        id=str(metric.id),
        server_id=metric.server_id,
        cpu_usage=metric.cpu_usage,
        memory_usage=metric.memory_usage,
        disk_usage=metric.disk_usage,
        memory_used=metric.memory_used,
        memory_available=metric.memory_available,
        disk_used=metric.disk_used,
        disk_available=metric.disk_available,
        network_received=metric.network_received,
        network_sent=metric.network_sent,
        uptime=metric.uptime,
        process_count=metric.process_count,
        load_average=metric.load_average,
        timestamp=metric.timestamp,
    )


@router.get(
    "/{server_id}/metrics",
    response_model=MetricListResponse,
    summary="Get server metrics",
)
async def get_metrics(
    server_id: str,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    metrics = await metric_repo.list_for_server(
        server_id, hours=hours, limit=limit, start_time=start_time, end_time=end_time
    )
    items = [_metric_response(m) for m in metrics]
    return MetricListResponse(items=items, total=len(items), limit=limit, hours=hours)


@router.get(
    "/{server_id}/metrics/latest",
    response_model=MetricResponse,
    summary="Get latest metric",
)
async def get_latest_metric(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    metric = await metric_repo.get_latest(server_id)
    if not metric:
        raise HTTPException(status_code=404, detail="No metrics found")
    return _metric_response(metric)
