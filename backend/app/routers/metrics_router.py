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
        cpu_count=metric.cpu_count,
        cpu_physical=metric.cpu_physical,
        cpu_frequency=metric.cpu_frequency,
        cpu_per_core=metric.cpu_per_core,
        memory_usage=metric.memory_usage,
        memory_used=metric.memory_used,
        memory_available=metric.memory_available,
        memory_total=metric.memory_total,
        memory_free=metric.memory_free,
        swap_total=metric.swap_total,
        swap_used=metric.swap_used,
        swap_percent=metric.swap_percent,
        disk_usage=metric.disk_usage,
        disk_used=metric.disk_used,
        disk_available=metric.disk_available,
        disk_total=metric.disk_total,
        disk_read_bytes=metric.disk_read_bytes,
        disk_write_bytes=metric.disk_write_bytes,
        disk_read_count=metric.disk_read_count,
        disk_write_count=metric.disk_write_count,
        network_received=metric.network_received,
        network_sent=metric.network_sent,
        packets_sent=metric.packets_sent,
        packets_received=metric.packets_received,
        errors_in=metric.errors_in,
        errors_out=metric.errors_out,
        dropped_in=metric.dropped_in,
        dropped_out=metric.dropped_out,
        network_interfaces=metric.network_interfaces,
        uptime=metric.uptime,
        load_average=metric.load_average,
        hostname=metric.hostname,
        operating_system=metric.operating_system,
        os_version=metric.os_version,
        architecture=metric.architecture,
        platform=metric.platform,
        python_version=metric.python_version,
        boot_time=metric.boot_time,
        processes=metric.processes,
        response_time_ms=metric.response_time_ms,
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
    skip: int = Query(0, ge=0),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
):
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    total_count = await metric_repo.count_for_server(
        server_id, hours=hours, start_time=start_time, end_time=end_time
    )
    metrics = await metric_repo.list_for_server(
        server_id, hours=hours, limit=limit, skip=skip, start_time=start_time, end_time=end_time
    )
    items = [_metric_response(m) for m in metrics]
    return MetricListResponse(items=items, total=total_count, limit=limit, hours=hours)


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
