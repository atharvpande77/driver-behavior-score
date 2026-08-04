from typing import Annotated

from fastapi import APIRouter, Depends

from src.auth.dependencies import get_current_dashboard_user
from src.core.dependencies import GetUsageRecorder, ValidateVehicleNumber
from src.dashboard.dependencies import get_dashboard_service
from src.dashboard.schemas import (
    BatchVehicleLookupRequest,
    BatchVehicleLookupResponse,
    VehicleLookupResponse,
)
from src.dashboard.service import DashboardService

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
    usage: GetUsageRecorder,
    dashboard_svc: Annotated[DashboardService, Depends(get_dashboard_service)],
):
    return await dashboard_svc.batch_vehicle_lookup(payload.vehicle_numbers, usage)


@router.get(
    "/lookup/{vehicle_number}",
    response_model=VehicleLookupResponse,
)
async def vehicle_lookup(
    vehicle_number: ValidateVehicleNumber,
    usage: GetUsageRecorder,
    dashboard_svc: Annotated[DashboardService, Depends(get_dashboard_service)],
):
    return await dashboard_svc.vehicle_lookup(vehicle_number, usage)