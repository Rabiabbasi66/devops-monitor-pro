from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_servers: int
    online_servers: int
    offline_servers: int
    warning_servers: int
    critical_servers: int
    pending_alerts: int
    critical_alerts: int
    average_cpu: float
    average_memory: float
    average_disk: float
    uptime_percentage: float

    # Backward compatibility aliases
    running_servers: int = 0
    stopped_servers: int = 0
    error_servers: int = 0
    alerts_pending: int = 0
    avg_cpu: float = 0.0
    avg_memory: float = 0.0
    avg_disk: float = 0.0


class HealthCheckResponse(BaseModel):
    status: str
    database: str
    monitoring_service: str
