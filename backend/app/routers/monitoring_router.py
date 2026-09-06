from fastapi import APIRouter, Header, HTTPException

from ..schemas.metric import MetricIngest
from ..services.monitoring_service import MonitoringService
from ..services.websocket_manager import ws_manager

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])
monitoring_service = MonitoringService()


@router.post("/metrics", summary="Ingest metrics from monitoring agent")
async def ingest_metrics(
    data: MetricIngest,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    try:
        result = await monitoring_service.ingest_metrics(data, x_agent_token)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Invalid agent token")

    server = result["server"]
    metric = result["metric"]
    alerts = result["alerts"]

    await ws_manager.broadcast(
        data.server_id,
        {
            "type": "metric",
            "server_id": data.server_id,
            "cpu_usage": server.cpu_usage,
            "memory_usage": server.memory_usage,
            "disk_usage": server.disk_usage,
            "status": server.status.value,
            "health_status": server.health_status.value,
            "timestamp": metric.timestamp.isoformat(),
        },
    )

    for alert in alerts:
        await ws_manager.broadcast(
            data.server_id,
            {
                "type": "alert",
                "alert_id": str(alert.id),
                "severity": alert.severity.value,
                "message": alert.message,
                "metric_type": alert.metric_type,
            },
        )

    return {
        "success": True,
        "message": "Metrics ingested",
        "alerts_created": len(alerts),
    }
