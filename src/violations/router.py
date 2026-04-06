from fastapi import APIRouter, Depends

from src.auth.dependencies import verify_api_key
from src.violations.dependencies import get_challan_service
from src.violations.service import ChallanService

from src.dependencies import ValidateVehicleNumber

router = APIRouter(
    tags=["public"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/{vehicle_number}"
)
async def get_violations(
    vehicle_number: ValidateVehicleNumber,
    challan_svc: ChallanService = Depends(get_challan_service),
):
    """Get active challans for the given vehicle number."""
    return await challan_svc.get_active_challans(vehicle_number)
