from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId

from ..models.alert_rule import AlertRule
from ..models.audit_log import AuditAction, AuditLog
from ..models.user import User
from ..schemas.alert_rule import AlertRuleCreate, AlertRuleUpdate


class AlertRuleService:
    async def create_rule(self, data: AlertRuleCreate, user: User, ip: Optional[str] = None) -> AlertRule:
        rule = AlertRule(
            name=data.name,
            description=data.description,
            user_id=str(user.id),
            server_id=data.server_id,
            metric_type=data.metric_type,
            operator=data.operator,
            warning_threshold=data.warning_threshold,
            critical_threshold=data.critical_threshold,
            evaluation_interval_seconds=data.evaluation_interval_seconds,
            cooldown_seconds=data.cooldown_seconds,
            enabled=data.enabled,
            severity=data.severity,
            notification_channels=data.notification_channels,
        )
        await rule.insert()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.ALERT_RULE_CREATED,
            resource_type="alert_rule",
            resource_id=str(rule.id),
            ip_address=ip,
        ).insert()
        
        return rule

    async def list_rules(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        server_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[AlertRule]:
        filters = [AlertRule.user_id == str(user.id)]
        
        if server_id:
            filters.append(AlertRule.server_id == server_id)
        
        if enabled_only:
            filters.append(AlertRule.enabled == True)
        
        return await AlertRule.find(*filters).skip(skip).limit(limit).to_list()

    async def get_rule(self, rule_id: str, user: User) -> Optional[AlertRule]:
        try:
            oid = PydanticObjectId(rule_id)
        except Exception:
            return None
        rule = await AlertRule.get(oid)
        if not rule or rule.user_id != str(user.id):
            return None
        return rule

    async def update_rule(
        self,
        rule_id: str,
        data: AlertRuleUpdate,
        user: User,
        ip: Optional[str] = None,
    ) -> Optional[AlertRule]:
        rule = await self.get_rule(rule_id, user)
        if not rule:
            return None
        
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        
        rule.updated_at = datetime.utcnow()
        await rule.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.ALERT_RULE_UPDATED,
            resource_type="alert_rule",
            resource_id=str(rule.id),
            ip_address=ip,
        ).insert()
        
        return rule

    async def delete_rule(self, rule_id: str, user: User, ip: Optional[str] = None) -> bool:
        rule = await self.get_rule(rule_id, user)
        if not rule:
            return False
        
        await rule.delete()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.ALERT_RULE_DELETED,
            resource_type="alert_rule",
            resource_id=str(rule.id),
            ip_address=ip,
        ).insert()
        
        return True

    async def enable_rule(self, rule_id: str, user: User, ip: Optional[str] = None) -> Optional[AlertRule]:
        rule = await self.get_rule(rule_id, user)
        if not rule:
            return None
        
        rule.enabled = True
        rule.updated_at = datetime.utcnow()
        await rule.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.SERVER_UPDATED,
            resource_type="alert_rule",
            resource_id=str(rule.id),
            ip_address=ip,
        ).insert()
        
        return rule

    async def disable_rule(self, rule_id: str, user: User, ip: Optional[str] = None) -> Optional[AlertRule]:
        rule = await self.get_rule(rule_id, user)
        if not rule:
            return None
        
        rule.enabled = False
        rule.updated_at = datetime.utcnow()
        await rule.save()
        
        await AuditLog(
            user_id=str(user.id),
            action=AuditAction.SERVER_UPDATED,
            resource_type="alert_rule",
            resource_id=str(rule.id),
            ip_address=ip,
        ).insert()
        
        return rule
