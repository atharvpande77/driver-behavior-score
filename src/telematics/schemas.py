from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ── Endpoint 1: Device list ───────────────────────────────────────────────────

class TelematicsDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    imei: str
    vehicle_reg_no: str
    last_seen_at: datetime | None


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int


class TelematicsDeviceListResponse(BaseModel):
    items: list[TelematicsDeviceResponse]
    meta: PaginationMeta


# ── Endpoint 2: Vehicle trips ─────────────────────────────────────────────────

class TripResponse(BaseModel):
    """Shared shape for the active trip and each recent closed trip."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime | None
    ended_at: datetime | None
    total_distance_km: float | None
    total_duration_seconds: int | None
    start_lat: float | None
    start_lon: float | None
    end_lat: float | None
    end_lon: float | None
    max_speed_kmph: float | None
    avg_speed_kmph: float | None


class VehicleTripsResponse(BaseModel):
    active_trip: TripResponse | None
    recent_trips: list[TripResponse]


# ── Endpoint 3: Vehicle driving stats ─────────────────────────────────────────

from pydantic import Field
from datetime import date


class DistanceStats(BaseModel):
    total_km: float
    avg_per_trip_km: float
    longest_trip_km: float
    shortest_trip_km: float
    day_km: float
    night_km: float
    night_pct: float


class DurationStats(BaseModel):
    total_seconds: int
    avg_per_trip_seconds: int
    longest_trip_seconds: int
    day_seconds: int
    night_seconds: int


class SpeedStats(BaseModel):
    max_kmph: float
    avg_kmph: float


class SafetyStats(BaseModel):
    harsh_acceleration: int
    harsh_braking: int
    harsh_turning: int
    total_harsh_events: int
    harsh_events_per_100km: float


class VehicleStatsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vehicle_reg_no: str
    range: str | None
    from_date: date = Field(serialization_alias="from")
    to_date: date = Field(serialization_alias="to")
    trips_included: int
    distance: DistanceStats
    duration: DurationStats
    speed: SpeedStats
    safety: SafetyStats

