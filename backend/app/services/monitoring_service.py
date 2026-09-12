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
            logger.warning("Invalid agent credentials attempt for server %s", data.server_id)
            raise PermissionError("Invalid agent credentials")

        was_offline = server.health_status == HealthStatus.OFFLINE
        now = datetime.utcnow()

        # Update server with latest metrics
        server.cpu_usage = data.cpu_usage
        server.memory_usage = data.memory_usage
        server.disk_usage = data.disk_usage
        server.uptime = data.uptime
        server.last_checked = now
        server.last_seen = now
        server.updated_at = now
        server.status = ServerStatus.RUNNING
        server.response_time_ms = data.response_time_ms
        
        # Update system information if provided
        if data.hostname:
            server.hostname = data.hostname
        if data.operating_system:
            server.operating_system = data.operating_system
        
        # Advanced system info storage in server document (optional fields)
        if data.os_version:
            server.os_version = data.os_version
        if data.architecture:
            server.architecture = data.architecture
        if data.platform:
            server.platform = data.platform
        
        # Track agent version and mark agent as active
        if data.agent_version:
            server.agent_version = data.agent_version
        server.agent_status = "active"
        
        server.health_status = self._compute_health(server)
        await server.save()

        # Store detailed metrics
        metric = await self.metric_repo.create(data)
        alerts = await self.alert_service.evaluate_metrics(server)

        if was_offline:
            logger.info("Server %s (%s) recovered from offline state", server.name, server.id)
            await self.alert_service.create_recovery_alert(server)
            # Broadcast recovery event via WebSocket
            from .websocket_manager import ws_manager
            await ws_manager.broadcast(
                str(server.id),
                {
                    "type": "health_change",
                    "server_id": str(server.id),
                    "health_status": server.health_status.value,
                    "status": server.status.value,
                    "event": "recovery",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        return {
            "metric": metric,
            "server": server,
            "alerts": alerts,
        }

    def _compute_health(self, server: Server) -> HealthStatus:
        """Compute comprehensive health status based on multiple factors."""
        # Check if server has recent metrics
        if not server.last_seen:
            return HealthStatus.UNKNOWN
        
        # Check if server is offline
        time_since_last_seen = datetime.utcnow() - server.last_seen
        if time_since_last_seen.total_seconds() > settings.SERVER_OFFLINE_THRESHOLD_SECONDS:
            return HealthStatus.OFFLINE
        
        t = server.thresholds
        
        # Critical conditions
        critical_conditions = [
            server.cpu_usage >= t.cpu_critical,
            server.memory_usage >= t.memory_critical,
            server.disk_usage >= t.disk_critical,
        ]
        
        if any(critical_conditions):
            return HealthStatus.CRITICAL
        
        # Warning conditions
        warning_conditions = [
            server.cpu_usage >= t.cpu_warning,
            server.memory_usage >= t.memory_warning,
            server.disk_usage >= t.disk_warning,
        ]
        
        if any(warning_conditions):
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
            # Broadcast offline status change via WebSocket
            from .websocket_manager import ws_manager
            await ws_manager.broadcast(
                str(server.id),
                {
                    "type": "health_change",
                    "server_id": str(server.id),
                    "health_status": HealthStatus.OFFLINE.value,
                    "status": server.status.value,
                    "event": "offline",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
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
        if total == 0:
            return {
                "total_servers": 0,
                "online_servers": 0,
                "offline_servers": 0,
                "warning_servers": 0,
                "critical_servers": 0,
                "pending_alerts": 0,
                "critical_alerts": 0,
                "average_cpu": 0,
                "average_memory": 0,
                "average_disk": 0,
                "uptime_percentage": 0,
                "running_servers": 0,
                "stopped_servers": 0,
                "error_servers": 0,
                "alerts_pending": 0,
                "avg_cpu": 0,
                "avg_memory": 0,
                "avg_disk": 0,
            }
        
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
        avg_cpu = sum(s.cpu_usage for s in servers) / total
        avg_memory = sum(s.memory_usage for s in servers) / total
        avg_disk = sum(s.disk_usage for s in servers) / total
        uptime_pct = (online / total * 100)
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
