from fastapi import APIRouter, Depends

from ..models.user import User
from ..schemas.dashboard import DashboardSummary
from ..services.monitoring_service import MonitoringService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
monitoring_service = MonitoringService()


@router.get("/summary", response_model=DashboardSummary, summary="Dashboard summary")
async def get_summary(current_user: User = Depends(get_current_active_user)):
    stats = await monitoring_service.get_dashboard_summary(current_user)
    return DashboardSummary(**stats)
