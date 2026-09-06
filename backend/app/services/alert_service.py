import logging
from datetime import datetime
from typing import List, Optional

from ..models.alert import Alert, AlertSeverity, AlertStatus
from ..models.audit_log import AuditAction, AuditLog
from ..models.notification import NotificationType
from ..models.server import HealthStatus, Server
from ..models.user import User, UserRole
from ..repositories.alert_repository import AlertRepository
from ..repositories.server_repository import ServerRepository
from .notification_service import NotificationService

logger = logging.getLogger("devops_monitor")


class AlertService:
    def __init__(self) -> None:
        self.alert_repo = AlertRepository()
        self.server_repo = ServerRepository()
        self.notification_service = NotificationService()

    async def evaluate_metrics(self, server: Server) -> List[Alert]:
        created: List[Alert] = []
        thresholds = server.thresholds
        checks = [
            ("cpu", server.cpu_usage, thresholds.cpu_warning, thresholds.cpu_critical),
            (
                "memory",
                server.memory_usage,
                thresholds.memory_warning,
                thresholds.memory_critical,
            ),
            (
                "disk",
                server.disk_usage,
                thresholds.disk_warning,
                thresholds.disk_critical,
            ),
        ]
        for metric_type, value, warning, critical in checks:
            if value >= critical:
                alert = await self._maybe_create_alert(
                    server, metric_type, value, critical, AlertSeverity.CRITICAL
                )
                if alert:
                    created.append(alert)
            elif value >= warning:
                alert = await self._maybe_create_alert(
                    server, metric_type, value, warning, AlertSeverity.HIGH
                )
                if alert:
                    created.append(alert)
        return created

    async def _maybe_create_alert(
        self,
        server: Server,
        metric_type: str,
        value: float,
        threshold: float,
        severity: AlertSeverity,
    ) -> Optional[Alert]:
        existing = await self.alert_repo.find_active_duplicate(
            str(server.id), metric_type, severity
        )
        if existing:
            return None
        message = f"High {metric_type} usage on {server.name}: {value:.1f}% (threshold {threshold:.1f}%)"
        alert = await self.alert_repo.create(
            server=server,
            message=message,
            severity=severity,
            metric_type=metric_type,
            current_value=value,
            threshold=threshold,
        )
        logger.warning("Alert created: %s", message)
        await self.notification_service.create_for_alert(server, alert)
        return alert

    async def create_offline_alert(self, server: Server) -> Optional[Alert]:
        existing = await self.alert_repo.find_active_duplicate(
            str(server.id), "connectivity", AlertSeverity.CRITICAL
        )
        if existing:
            return None
        alert = await self.alert_repo.create(
            server=server,
            message=f"Server {server.name} is offline",
            severity=AlertSeverity.CRITICAL,
            metric_type="connectivity",
            current_value=0,
            threshold=0,
        )
        server.health_status = HealthStatus.OFFLINE
        server.status = server.status
        await server.save()
        await self.notification_service.create_for_alert(server, alert)
        return alert

    async def create_recovery_alert(self, server: Server) -> Optional[Alert]:
        alert = await self.alert_repo.create(
            server=server,
            message=f"Server {server.name} recovered",
            severity=AlertSeverity.INFO,
            metric_type="connectivity",
            current_value=1,
            threshold=0,
        )
        alert.status = AlertStatus.RESOLVED
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        await alert.save()
        await self.notification_service.create_recovery(server)
        return alert

    async def list_alerts(
        self, user: User, pending_only: bool = False, skip: int = 0, limit: int = 100
    ) -> List[Alert]:
        admin = user.role == UserRole.ADMIN
        servers = await self.server_repo.list_for_user(
            str(user.id), admin=admin, limit=1000
        )
        server_ids = [str(s.id) for s in servers]
        return await self.alert_repo.list_for_servers(
            server_ids, pending_only=pending_only, skip=skip, limit=limit
        )

    async def get_alert_for_user(self, alert_id: str, user: User) -> Optional[Alert]:
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            return None
        server = await self.server_repo.get_by_id(
            alert.server_id, str(user.id), admin=user.role == UserRole.ADMIN
        )
        if not server:
            return None
        return alert

    async def acknowledge(self, alert: Alert, user: User, ip: Optional[str] = None) -> Alert:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        await alert.save()
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.ALERT_ACKNOWLEDGED,
            resource_type="alert",
            resource_id=str(alert.id),
            ip_address=ip,
        ).insert()
        return alert

    async def resolve(self, alert: Alert, user: User, ip: Optional[str] = None) -> Alert:
        alert.status = AlertStatus.RESOLVED
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        await alert.save()
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.ALERT_RESOLVED,
            resource_type="alert",
            resource_id=str(alert.id),
            ip_address=ip,
        ).insert()
        return alert

    async def reopen(self, alert: Alert, user: User, ip: Optional[str] = None) -> Alert:
        alert.status = AlertStatus.PENDING
        alert.resolved = False
        alert.resolved_at = None
        alert.acknowledged_at = None
        await alert.save()
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.ALERT_REOPENED,
            resource_type="alert",
            resource_id=str(alert.id),
            ip_address=ip,
        ).insert()
        return alert
