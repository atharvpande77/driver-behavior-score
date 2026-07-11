from datetime import date
from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_dashboard_user
from src.telematics.dependencies import GetTelematicsService
from src.telematics.schemas import (
    TelematicsDeviceListResponse,
    TelematicsDeviceResponse,
    PaginationMeta,
    TripResponse,
    VehicleTripsResponse,
    VehicleStatsResponse,
)
from src.telematics.types import PaginationParams


router = APIRouter(
    prefix="",
    tags=["telematics"],
    dependencies=[Depends(get_current_dashboard_user)],
)


@router.get("/vehicles", response_model=TelematicsDeviceListResponse)
async def list_telematics_vehicles(
    telematics_svc: GetTelematicsService,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Paginated list of telematics devices with IMEI, vehicle reg number, and last seen timestamp."""
    params = PaginationParams(page=page, limit=limit)
    items, total = await telematics_svc.list_devices(params)
    return TelematicsDeviceListResponse(
        items=[TelematicsDeviceResponse.model_validate(d) for d in items],
        meta=PaginationMeta(page=page, limit=limit, total=total),
    )


@router.get("/vehicles/{vehicle_reg_number}/trips", response_model=VehicleTripsResponse)
async def get_vehicle_trips(
    vehicle_reg_number: str,
    telematics_svc: GetTelematicsService,
):
    """Return the active trip (if any) and the 10 most recent closed trips for a vehicle."""
    active_trip, recent_trips = await telematics_svc.get_vehicle_trips(vehicle_reg_number)
    return VehicleTripsResponse(
        active_trip=TripResponse.model_validate(active_trip) if active_trip else None,
        recent_trips=[TripResponse.model_validate(t) for t in recent_trips],
    )


@router.get("/vehicles/{vehicle_reg_number}/stats", response_model=VehicleStatsResponse)
async def get_vehicle_stats(
    vehicle_reg_number: str,
    telematics_svc: GetTelematicsService,
    range_preset: str | None = Query(default=None, alias="range"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    """
    Aggregated driving statistics for a vehicle over a date range.
    Use ?range=today|last_7_days|last_30_days  OR  ?from=YYYY-MM-DD&to=YYYY-MM-DD.
    """
    result = await telematics_svc.get_vehicle_stats(
        vehicle_reg_number, range_preset, from_date, to_date
    )
    return VehicleStatsResponse(**result)

