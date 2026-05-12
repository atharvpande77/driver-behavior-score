from fastapi import APIRouter

from src.auth.dependencies import GetCurrentDashboardUser
from src.usage.dependencies import GetUsageEventService
from src.usage.schemas import (
    UsageApiKeyStatsResponse,
    UsageRecentVehicleResponse,
    UsageSummaryResponse,
)


router = APIRouter(tags=["dashboard", "usage"])


@router.get(
    "/recent-vehicles",
    response_model=list[UsageRecentVehicleResponse],
)
async def recent_vehicle_queries(
    current_user: GetCurrentDashboardUser,
    usage_svc: GetUsageEventService,
):
    return await usage_svc.get_recent_vehicle_queries(current_user.id)


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
)
async def usage_summary(
    current_user: GetCurrentDashboardUser,
    usage_svc: GetUsageEventService,
):
    return await usage_svc.get_usage_summary(current_user.id)


@router.get(
    "/api-keys",
    response_model=list[UsageApiKeyStatsResponse],
)
async def api_key_usage(
    current_user: GetCurrentDashboardUser,
    usage_svc: GetUsageEventService,
):
    return await usage_svc.get_api_key_usage(current_user.id)