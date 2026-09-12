import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import close_db, init_db, ping_database
from .middleware.error_handler import (
    APIError,
    api_error_handler,
    general_exception_handler,
    http_exception_handler,
    validation_error_handler,
)
from .middleware.logging import RequestLoggingMiddleware, setup_logging
from .models import MODELS
from .routers import (
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
from .routers.notification_settings_router import router as notification_settings_router
from .routers.alert_rules_router import router as alert_rules_router
from .routers.incidents_router import router as incidents_router
from .schemas.dashboard import HealthCheckResponse
from .services.monitoring_service import MonitoringService

logger = logging.getLogger("devops_monitor")
monitoring_service = MonitoringService()
_background_task: asyncio.Task | None = None


async def _background_monitoring_loop():
    monitoring_service.set_running(True)
    while True:
        try:
            await monitoring_service.check_offline_servers()
            await monitoring_service.cleanup_metrics()
        except Exception:
            logger.exception("Background monitoring task failed")
        await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.DEBUG)
    logger.info("Starting DevOps Monitor Pro...")
    await init_db(MODELS)
    global _background_task
    _background_task = asyncio.create_task(_background_monitoring_loop())
    yield
    logger.info("Shutting down...")
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass
    monitoring_service.set_running(False)
    await close_db()


app = FastAPI(
    title="DevOps Monitor Pro API",
    description="Production-ready DevOps infrastructure monitoring platform",
    version="2.0.0",
    lifespan=lifespan,
)

# Register exception handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

origins = [settings.FRONTEND_URL]
if settings.ENVIRONMENT == "development":
    origins.extend([
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
    ])
if settings.ALLOWED_ORIGINS != ["*"]:
    origins.extend(settings.ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

api_prefix = "/api"
app.include_router(auth_router.router, prefix=api_prefix)
app.include_router(server_router.router, prefix=api_prefix)
app.include_router(metrics_router.router, prefix=api_prefix)
app.include_router(alerts_router.router, prefix=api_prefix)
app.include_router(alert_rules_router, prefix=api_prefix)
app.include_router(incidents_router, prefix=api_prefix)
app.include_router(monitoring_router.router, prefix=api_prefix)
app.include_router(dashboard_router.router, prefix=api_prefix)
app.include_router(notifications_router.router, prefix=api_prefix)
app.include_router(notification_settings_router, prefix=api_prefix)
app.include_router(audit_router.router, prefix=api_prefix)
app.include_router(admin_router.router, prefix=api_prefix)
app.include_router(websocket_router.router, prefix=api_prefix)
app.include_router(agent_enrollment_router.router, prefix=api_prefix)


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "DevOps Monitor Pro API",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    db_ok = await ping_database()
    return HealthCheckResponse(
        status="healthy" if db_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        monitoring_service="running" if monitoring_service.is_running else "stopped",
    )