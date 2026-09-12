from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId

from ..models.incident import Incident, IncidentStatus, IncidentSeverity
from ..models.audit_log import AuditAction, AuditLog
from ..models.user import User
from ..models.alert import Alert
from ..schemas.incident import IncidentCreate, IncidentUpdate


class IncidentService:
    async def create_incident(self, data: IncidentCreate, user: User, ip: Optional[str] = None) -> Incident:
        incident = Incident(
            title=data.title,
            description=data.description,
            user_id=str(user.id),
            severity=data.severity,
            status=IncidentStatus.OPEN,
            affected_servers=data.affected_servers,
            related_alerts=data.related_alerts,
        )
        await incident.insert()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.INCIDENT_CREATED,
            resource_type="incident",
            resource_id=str(incident.id),
            ip_address=ip,
        ).insert()
        
        return incident

    async def list_incidents(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
    ) -> List[Incident]:
        filters = [Incident.user_id == str(user.id)]
        
        if status:
            filters.append(Incident.status == status)
        
        if severity:
            filters.append(Incident.severity == severity)
        
        return await Incident.find(*filters).sort(-Incident.created_at).skip(skip).limit(limit).to_list()

    async def get_incident(self, incident_id: str, user: User) -> Optional[Incident]:
        try:
            oid = PydanticObjectId(incident_id)
        except Exception:
            return None
        incident = await Incident.get(oid)
        if not incident or incident.user_id != str(user.id):
            return None
        return incident

    async def update_incident(
        self,
        incident_id: str,
        data: IncidentUpdate,
        user: User,
        ip: Optional[str] = None,
    ) -> Optional[Incident]:
        incident = await self.get_incident(incident_id, user)
        if not incident:
            return None
        
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(incident, key, value)
        
        incident.updated_at = datetime.utcnow()
        await incident.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.INCIDENT_UPDATED,
            resource_type="incident",
            resource_id=str(incident.id),
            ip_address=ip,
        ).insert()
        
        return incident

    async def acknowledge_incident(self, incident_id: str, user: User, ip: Optional[str] = None) -> Optional[Incident]:
        incident = await self.get_incident(incident_id, user)
        if not incident:
            return None
        
        incident.status = IncidentStatus.INVESTIGATING
        incident.acknowledged_at = datetime.utcnow()
        incident.acknowledged_by = str(user.id)
        incident.updated_at = datetime.utcnow()
        await incident.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.INCIDENT_UPDATED,
            resource_type="incident",
            resource_id=str(incident.id),
            ip_address=ip,
        ).insert()
        
        return incident

    async def resolve_incident(self, incident_id: str, user: User, ip: Optional[str] = None) -> Optional[Incident]:
        incident = await self.get_incident(incident_id, user)
        if not incident:
            return None
        
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.resolved_by = str(user.id)
        incident.updated_at = datetime.utcnow()
        
        # Calculate duration
        if incident.created_at:
            incident.duration_seconds = (incident.resolved_at - incident.created_at).total_seconds()
        
        await incident.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.INCIDENT_RESOLVED,
            resource_type="incident",
            resource_id=str(incident.id),
            ip_address=ip,
        ).insert()
        
        return incident

    async def reopen_incident(self, incident_id: str, user: User, ip: Optional[str] = None) -> Optional[Incident]:
        incident = await self.get_incident(incident_id, user)
        if not incident:
            return None
        
        incident.status = IncidentStatus.OPEN
        incident.resolved_at = None
        incident.resolved_by = None
        incident.acknowledged_at = None
        incident.acknowledged_by = None
        incident.updated_at = datetime.utcnow()
        await incident.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.INCIDENT_UPDATED,
            resource_type="incident",
            resource_id=str(incident.id),
            ip_address=ip,
        ).insert()
        
        return incident

    async def delete_incident(self, incident_id: str, user: User, ip: Optional[str] = None) -> bool:
        incident = await self.get_incident(incident_id, user)
        if not incident:
            return False
        
        await incident.delete()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.SERVER_DELETED,  # Reusing existing action
            resource_type="incident",
            resource_id=str(incident.id),
            ip_address=ip,
        ).insert()
        
        return True

    async def link_alert_to_incident(self, incident_id: str, alert_id: str, user: User) -> Optional[Incident]:
        incident = await self.get_incident(incident_id, user)
        if not incident:
            return None
        
        if alert_id not in incident.related_alerts:
            incident.related_alerts.append(alert_id)
            incident.updated_at = datetime.utcnow()
            await incident.save()
        
        return incident
