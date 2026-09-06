import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import settings
from ..models.alert import AlertSeverity
from ..models.server import HealthStatus, Server, ServerStatus
from ..models.user import User, UserRole
from ..repositories.metric_repository import MetricRepository
from ..repositories.server_repository import ServerRepository
from ..schemas.metric import MetricIngest
from .alert_service import AlertService

logger = logging.getLogger("devops_monitor")


class MonitoringService:
    def __init__(self) -> None:
        self.metric_repo = MetricRepository()
        self.server_repo = ServerRepository()
        self.alert_service = AlertService()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def set_running(self, value: bool) -> None:
        self._running = value

    async def ingest_metrics(
        self, data: MetricIngest, agent_token: str
    ) -> Dict[str, Any]:
        server = await self.server_repo.get_by_agent_token(agent_token)
        if not server or str(server.id) != data.server_id:
            raise PermissionError("Invalid agent credentials")

        was_offline = server.health_status == HealthStatus.OFFLINE
        now = datetime.utcnow()

        server.cpu_usage = data.cpu_usage
        server.memory_usage = data.memory_usage
        server.disk_usage = data.disk_usage
        server.uptime = data.uptime
        server.last_checked = now
        server.last_seen = now
        server.updated_at = now
        server.status = ServerStatus.RUNNING
        server.response_time_ms = data.response_time_ms
        if data.hostname:
            server.hostname = data.hostname
        if data.operating_system:
            server.operating_system = data.operating_system
        server.health_status = self._compute_health(server)
        await server.save()

        metric = await self.metric_repo.create(data)
        alerts = await self.alert_service.evaluate_metrics(server)

        if was_offline:
            await self.alert_service.create_recovery_alert(server)

        return {
            "metric": metric,
            "server": server,
            "alerts": alerts,
        }

    def _compute_health(self, server: Server) -> HealthStatus:
        t = server.thresholds
        if (
            server.cpu_usage >= t.cpu_critical
            or server.memory_usage >= t.memory_critical
            or server.disk_usage >= t.disk_critical
        ):
            return HealthStatus.CRITICAL
        if (
            server.cpu_usage >= t.cpu_warning
            or server.memory_usage >= t.memory_warning
            or server.disk_usage >= t.disk_warning
        ):
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY

    async def check_offline_servers(self) -> List[Server]:
        cutoff = datetime.utcnow() - timedelta(
            seconds=settings.SERVER_OFFLINE_THRESHOLD_SECONDS
        )
        servers = await Server.find(
            Server.last_seen != None,  # noqa: E711
            Server.last_seen < cutoff,
            Server.health_status != HealthStatus.OFFLINE,
        ).to_list()
        for server in servers:
            await self.alert_service.create_offline_alert(server)
        return servers

    async def cleanup_metrics(self) -> int:
        deleted = await self.metric_repo.cleanup_old()
        if deleted:
            logger.info("Cleaned up %s old metrics", deleted)
        return deleted

    async def get_dashboard_summary(self, user: User) -> Dict[str, Any]:
        admin = user.role == UserRole.ADMIN
        servers = await self.server_repo.list_for_user(
            str(user.id), admin=admin, limit=1000
        )
        total = len(servers)
        online = sum(
            1
            for s in servers
            if s.health_status not in (HealthStatus.OFFLINE, HealthStatus.UNKNOWN)
        )
        offline = sum(1 for s in servers if s.health_status == HealthStatus.OFFLINE)
        warning = sum(1 for s in servers if s.health_status == HealthStatus.WARNING)
        critical = sum(1 for s in servers if s.health_status == HealthStatus.CRITICAL)
        server_ids = [str(s.id) for s in servers]
        pending = await self.alert_service.alert_repo.count_for_servers(
            server_ids, pending_only=True
        )
        critical_alerts = await self.alert_service.alert_repo.count_for_servers(
            server_ids, severity=AlertSeverity.CRITICAL
        )
        avg_cpu = sum(s.cpu_usage for s in servers) / total if total else 0
        avg_memory = sum(s.memory_usage for s in servers) / total if total else 0
        avg_disk = sum(s.disk_usage for s in servers) / total if total else 0
        uptime_pct = (online / total * 100) if total else 0
        running = sum(1 for s in servers if s.status == ServerStatus.RUNNING)
        stopped = sum(1 for s in servers if s.status == ServerStatus.STOPPED)
        error = sum(1 for s in servers if s.status == ServerStatus.ERROR)
        return {
            "total_servers": total,
            "online_servers": online,
            "offline_servers": offline,
            "warning_servers": warning,
            "critical_servers": critical,
            "pending_alerts": pending,
            "critical_alerts": critical_alerts,
            "average_cpu": round(avg_cpu, 2),
            "average_memory": round(avg_memory, 2),
            "average_disk": round(avg_disk, 2),
            "uptime_percentage": round(uptime_pct, 2),
            "running_servers": running,
            "stopped_servers": stopped,
            "error_servers": error,
            "alerts_pending": pending,
            "avg_cpu": round(avg_cpu, 2),
            "avg_memory": round(avg_memory, 2),
            "avg_disk": round(avg_disk, 2),
        }
