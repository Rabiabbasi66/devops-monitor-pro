from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..models.user import User
from ..schemas.alert_rule import AlertRuleCreate, AlertRuleResponse, AlertRuleUpdate
from ..services.alert_rule_service import AlertRuleService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/alert-rules", tags=["Alert Rules"])
alert_rule_service = AlertRuleService()


def _serialize_rule(rule) -> AlertRuleResponse:
    return AlertRuleResponse(
        id=str(rule.id),
        name=rule.name,
        description=rule.description,
        user_id=rule.user_id,
        server_id=rule.server_id,
        metric_type=rule.metric_type,
        operator=rule.operator,
        warning_threshold=rule.warning_threshold,
        critical_threshold=rule.critical_threshold,
        evaluation_interval_seconds=rule.evaluation_interval_seconds,
        cooldown_seconds=rule.cooldown_seconds,
        enabled=rule.enabled,
        severity=rule.severity,
        notification_channels=rule.notification_channels,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.post("/", response_model=AlertRuleResponse, summary="Create alert rule")
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    rule = await alert_rule_service.create_rule(
        rule_data, current_user, ip=request.client.host if request.client else None
    )
    return _serialize_rule(rule)


@router.get("/", response_model=List[AlertRuleResponse], summary="List alert rules")
async def list_alert_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    server_id: Optional[str] = None,
    enabled_only: bool = False,
    current_user: User = Depends(get_current_active_user),
):
    rules = await alert_rule_service.list_rules(
        current_user, skip=skip, limit=limit, server_id=server_id, enabled_only=enabled_only
    )
    return [_serialize_rule(r) for r in rules]


@router.get("/{rule_id}", response_model=AlertRuleResponse, summary="Get alert rule")
async def get_alert_rule(
    rule_id: str,
    current_user: User = Depends(get_current_active_user),
):
    rule = await alert_rule_service.get_rule(rule_id, current_user)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return _serialize_rule(rule)


@router.put("/{rule_id}", response_model=AlertRuleResponse, summary="Update alert rule")
async def update_alert_rule(
    rule_id: str,
    update_data: AlertRuleUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    rule = await alert_rule_service.update_rule(
        rule_id, update_data, current_user, ip=request.client.host if request.client else None
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return _serialize_rule(rule)


@router.delete("/{rule_id}", summary="Delete alert rule")
async def delete_alert_rule(
    rule_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    success = await alert_rule_service.delete_rule(
        rule_id, current_user, ip=request.client.host if request.client else None
    )
    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"success": True, "message": "Alert rule deleted successfully"}


@router.post("/{rule_id}/enable", response_model=AlertRuleResponse, summary="Enable alert rule")
async def enable_alert_rule(
    rule_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    rule = await alert_rule_service.enable_rule(
        rule_id, current_user, ip=request.client.host if request.client else None
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return _serialize_rule(rule)


@router.post("/{rule_id}/disable", response_model=AlertRuleResponse, summary="Disable alert rule")
async def disable_alert_rule(
    rule_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    rule = await alert_rule_service.disable_rule(
        rule_id, current_user, ip=request.client.host if request.client else None
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return _serialize_rule(rule)
