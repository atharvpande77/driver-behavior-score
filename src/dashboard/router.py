from fastapi import APIRouter, Depends

from src.dashboard.dependencies import get_dashboard_service
from src.dashboard.service import DashboardService
from src.dashboard.schemas import (
    BatchVehicleLookupRequest,
    BatchVehicleLookupResponse,
    VehicleLookupResponse,
)

from src.auth.dependencies import get_current_dashboard_user
from src.dependencies import ValidateVehicleNumber


router = APIRouter(
    dependencies=[Depends(get_current_dashboard_user)],
    tags=["dashboard"]
)


@router.post(
    "/lookup/batch",
    response_model=BatchVehicleLookupResponse,
)
async def batch_vehicle_lookup(
    payload: BatchVehicleLookupRequest,
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    include_rc: bool = True,
):
    return await dashboard_svc.batch_vehicle_lookup(payload.vehicle_numbers, include_rc)


@router.get(
    "/lookup/{vehicle_number}",
    response_model=VehicleLookupResponse,
)
async def vehicle_lookup(
    vehicle_number: ValidateVehicleNumber,
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    include_rc: bool = True,
):
    return await dashboard_svc.vehicle_lookup(vehicle_number, include_rc)