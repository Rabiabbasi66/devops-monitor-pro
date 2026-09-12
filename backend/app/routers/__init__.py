from . import (
    admin_router,
    alerts_router,
    audit_router,
    auth_router,
    dashboard_router,
    metrics_router,
    monitoring_router,
    notifications_router,
    server_router,
    websocket_router,
    agent_enrollment_router,
)

__all__ = [
    "admin_router",
    "alerts_router",
    "audit_router",
    "auth_router",
    "dashboard_router",
    "metrics_router",
    "monitoring_router",
    "notifications_router",
    "server_router",
    "websocket_router",
    "agent_enrollment_router",
]
# Note: alert_rules_router, incidents_router, notification_settings_router
# are imported directly in main.py as router objects (not modules).
