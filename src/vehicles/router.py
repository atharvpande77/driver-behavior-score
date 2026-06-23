from fastapi import APIRouter, Depends

from src.auth.dependencies import verify_api_key
from src.vehicles.dependencies import get_vehicle_service
from src.vehicles.service import VehicleService
from src.core.dependencies import ValidateVehicleNumber
from src.vehicles.schemas import VehicleResponse
from src.core.dependencies import GetUsageRecorder


router = APIRouter(
    tags=["public"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/{vehicle_number}",
    response_model=VehicleResponse
)
async def get_vehicle(
    vehicle_number: ValidateVehicleNumber,
    usage: GetUsageRecorder,
    vehicle_svc: VehicleService = Depends(get_vehicle_service),
):
    """Get RC data for the given vehicle number."""
    return await vehicle_svc.get_vehicle(vehicle_number, usage=usage)
