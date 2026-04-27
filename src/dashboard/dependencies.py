from typing import Annotated
from fastapi import Depends

from src.dashboard.service import DashboardService

from src.violations.dependencies import GetChallanService
from src.score.dependencies import GetScoreService
from src.vehicles.dependencies import GetVehicleService
from src.database import async_session


def get_dashboard_service(
    challan_svc: GetChallanService,
    score_svc: GetScoreService,
    vehicle_svc: GetVehicleService,
):
    return DashboardService(
        challan_svc=challan_svc,
        score_svc=score_svc,
        vehicle_svc=vehicle_svc,
        session_factory=async_session,
    )
    
GetDashboardService = Annotated[DashboardService, Depends(get_dashboard_service)]
