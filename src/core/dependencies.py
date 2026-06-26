# Global dependencies
import httpx
from dataclasses import asdict
from fastapi import Depends, HTTPException, Request, status
from typing import Annotated

from src.core.types import UsageStatsPerVehicle
from src.core.utils import serialize_vehicle_number


def validate_vehicle_number(request: Request):
    vehicle_number = request.path_params.get("vehicle_number")
    if not vehicle_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing vehicle number.",
        )
    try:
        return serialize_vehicle_number(vehicle_number)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
        
        
async def get_http_client(request: Request):
    http_client = getattr(request.state, "http_client", None)
    if not http_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Internal Server Error", "detail": "No HTTP client initialized in lifespan."},
        )
    return http_client


class UsageRecorder:
    def __init__(self, request: Request):
        self.request = request
        if not getattr(self.request.state, "collect_usage", True):
            return
        if not hasattr(self.request.state, "stats_per_vehicle"):
            self.request.state.stats_per_vehicle = []

    def store_usage(self, stats_per_vehicle: list[UsageStatsPerVehicle]) -> None:
        if not getattr(self.request.state, "collect_usage", True):
            return
        self.request.state.stats_per_vehicle.extend(
            asdict(stat) for stat in stats_per_vehicle
        )

    def add(self, stats_per_vehicle: list[UsageStatsPerVehicle]) -> None:
        self.store_usage(stats_per_vehicle)


def get_usage_recorder(request: Request) -> UsageRecorder:
    return UsageRecorder(request)


ValidateVehicleNumber = Annotated[str, Depends(validate_vehicle_number)]
GetHttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
GetUsageRecorder = Annotated[UsageRecorder, Depends(get_usage_recorder)]
