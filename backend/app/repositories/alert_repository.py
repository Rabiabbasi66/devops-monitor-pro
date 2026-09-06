from datetime import datetime, timedelta
from typing import List, Optional

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In

from ..config import settings
from ..models.alert import Alert, AlertSeverity, AlertStatus
from ..models.server import Server


class AlertRepository:
    async def create(
        self,
        server: Server,
        message: str,
        severity: AlertSeverity,
        metric_type: str,
        current_value: float,
        threshold: float,
    ) -> Alert:
        alert = Alert(
            server_id=str(server.id),
            server_name=server.name,
            message=message,
            severity=severity,
            metric_type=metric_type,
            current_value=current_value,
            threshold=threshold,
        )
        await alert.insert()
        return alert

    async def find_active_duplicate(
        self, server_id: str, metric_type: str, severity: AlertSeverity
    ) -> Optional[Alert]:
        cutoff = datetime.utcnow() - timedelta(seconds=settings.ALERT_COOLDOWN_SECONDS)
        return await Alert.find(
            Alert.server_id == server_id,
            Alert.metric_type == metric_type,
            Alert.severity == severity,
            Alert.status != AlertStatus.RESOLVED,
            Alert.created_at >= cutoff,
        ).sort(-Alert.created_at).limit(1).first_or_none()

    async def list_for_servers(
        self,
        server_ids: List[str],
        pending_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Alert]:
        if not server_ids:
            return []
        filters = [In(Alert.server_id, server_ids)]
        if pending_only:
            filters.append(Alert.status == AlertStatus.PENDING)
        return await Alert.find(*filters).sort(-Alert.created_at).skip(skip).limit(limit).to_list()

    async def get_by_id(self, alert_id: str) -> Optional[Alert]:
        try:
            return await Alert.get(PydanticObjectId(alert_id))
        except Exception:
            return None

    async def count_for_servers(
        self,
        server_ids: List[str],
        severity: Optional[AlertSeverity] = None,
        pending_only: bool = False,
    ) -> int:
        if not server_ids:
            return 0
        filters = [In(Alert.server_id, server_ids)]
        if pending_only:
            filters.append(Alert.status == AlertStatus.PENDING)
        else:
            filters.append(Alert.status != AlertStatus.RESOLVED)
        if severity:
            filters.append(Alert.severity == severity)
        return await Alert.find(*filters).count()
