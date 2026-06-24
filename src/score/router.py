from fastapi import APIRouter, Depends, Request

from src.auth.dependencies import verify_api_key
from src.score.dependencies import get_score_service
from src.score.service import ScoreService
from src.score.schemas import DBSWithPremiumResponse
from src.core.dependencies import ValidateVehicleNumber
from src.core.dependencies import GetUsageRecorder
from src.core.rate_limit import limiter, key_by_api_key_or_ip
from src.core.config import app_settings


router = APIRouter(
    tags=["public"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/{vehicle_number}",
    response_model=DBSWithPremiumResponse
)
@limiter.limit(app_settings.PUBLIC_SCORE_RATE_LIMIT, key_func=key_by_api_key_or_ip)
async def score_controller(
    request: Request,
    vehicle_number: ValidateVehicleNumber,
    usage: GetUsageRecorder,
    score_svc: ScoreService = Depends(get_score_service),
):
    """Get the DBS score for the given vehicle number."""
    return await score_svc.get_score_response(vehicle_number, usage)
