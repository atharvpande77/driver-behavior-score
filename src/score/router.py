from fastapi import APIRouter, Depends

from src.auth.dependencies import verify_api_key
from src.score.dependencies import get_score_service
from src.score.service import ScoreService
from src.score.schemas import DBSWithPremiumResponse
from src.dependencies import ValidateVehicleNumber


router = APIRouter(
    tags=["public"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/{vehicle_number}",
    response_model=DBSWithPremiumResponse
)
async def score_controller(
    vehicle_number: ValidateVehicleNumber,
    score_svc: ScoreService = Depends(get_score_service),
):
    """Get the DBS score for the given vehicle number."""
    return await score_svc.get_score_response(vehicle_number)
