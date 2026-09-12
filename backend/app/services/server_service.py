from datetime import datetime
from typing import List, Optional

from ..models.audit_log import AuditAction, AuditLog
from ..models.server import Server
from ..models.user import User, UserRole
from ..repositories.server_repository import ServerRepository
from ..schemas.server import ServerCreate, ServerStatusUpdate, ServerUpdate
from ..schemas.server import ServerResponse


def serialize_server(server: Server, include_token: bool = False) -> ServerResponse:
    return ServerResponse(
        id=str(server.id),
        name=server.name,
        ip_address=server.ip_address,
        server_type=server.server_type,
        status=server.status,
        health_status=server.health_status,
        hostname=server.hostname,
        operating_system=server.operating_system,
        os_version=server.os_version,
        architecture=server.architecture,
        platform=server.platform,
        cpu_usage=server.cpu_usage,
        memory_usage=server.memory_usage,
        disk_usage=server.disk_usage,
        uptime=server.uptime,
        response_time_ms=server.response_time_ms,
        last_checked=server.last_checked,
        last_seen=server.last_seen,
        agent_version=server.agent_version,
        agent_status=server.agent_status,
        tags=server.tags,
        environment=server.environment,
        description=server.description,
        location=server.location,
        owner=server.owner,
        monitoring_enabled=server.monitoring_enabled,
        user_id=server.user_id,
        agent_token=server.agent_token if include_token and server.agent_token else None,
        thresholds=server.thresholds,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


class ServerService:
    def __init__(self) -> None:
        self.repo = ServerRepository()

    async def create(
        self, data: ServerCreate, user: User, ip: Optional[str] = None
    ) -> Server:
        server = await self.repo.create(data, str(user.id))
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.SERVER_CREATED,
            resource_type="server",
            resource_id=str(server.id),
            ip_address=ip,
        ).insert()
        return server

    async def list_servers(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[Server]:
        admin = user.role == UserRole.ADMIN
        return await self.repo.list_for_user(
            str(user.id), skip=skip, limit=limit, status=status, admin=admin
        )

    async def get_server(self, server_id: str, user: User) -> Optional[Server]:
        admin = user.role == UserRole.ADMIN
        return await self.repo.get_by_id(server_id, str(user.id), admin=admin)

    async def update_server(
        self,
        server: Server,
        data: ServerUpdate,
        user: User,
        ip: Optional[str] = None,
    ) -> Server:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(server, key, value)
        server.updated_at = datetime.utcnow()
        await server.save()
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.SERVER_UPDATED,
            resource_type="server",
            resource_id=str(server.id),
            ip_address=ip,
        ).insert()
        return server

    async def update_status(
        self,
        server: Server,
        data: ServerStatusUpdate,
        user: User,
        ip: Optional[str] = None,
    ) -> Server:
        server.status = data.status
        server.cpu_usage = data.cpu_usage
        server.memory_usage = data.memory_usage
        server.disk_usage = data.disk_usage
        server.last_checked = datetime.utcnow()
        server.last_seen = datetime.utcnow()
        server.updated_at = datetime.utcnow()
        await server.save()
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.STATUS_CHANGED,
            resource_type="server",
            resource_id=str(server.id),
            ip_address=ip,
        ).insert()
        return server

    async def delete_server(
        self, server: Server, user: User, ip: Optional[str] = None
    ) -> None:
        # Cascade delete related data
        server_id = str(server.id)

        # Delete metrics for this server
        from ..models.metric import Metric
        await Metric.find(Metric.server_id == server_id).delete()

        # Delete alerts for this server
        from ..models.alert import Alert
        await Alert.find(Alert.server_id == server_id).delete()

        # Delete in-app notifications that reference this server's alerts
        # (NotificationChannelConfig is user-level config — do NOT delete it)
        from ..models.notification import Notification
        # Notifications reference alert_id not server_id directly; cascade is best-effort
        # Only delete notifications that are directly linkable via server context
        # We leave notification channel config untouched (it's a user-level setting)

        # Delete incidents that only affect this server
        from ..models.incident import Incident
        await Incident.find(Incident.affected_servers == server_id).delete()

        # Delete enrollment tokens for this server
        from ..models.agent_enrollment import AgentEnrollment
        await AgentEnrollment.find(AgentEnrollment.server_id == server_id).delete()

        # Finally delete the server itself
        await self.repo.delete(server)

        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.SERVER_DELETED,
            resource_type="server",
            resource_id=str(server.id),
            ip_address=ip,
        ).insert()

    async def update_thresholds(
        self, server: Server, thresholds, user: User, ip: Optional[str] = None
    ) -> Server:
        server.thresholds = thresholds
        server.updated_at = datetime.utcnow()
        await server.save()
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.THRESHOLD_CHANGED,
            resource_type="server",
            resource_id=str(server.id),
            ip_address=ip,
        ).insert()
        return server
