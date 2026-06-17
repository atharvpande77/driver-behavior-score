import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EventRow:
    """Minimal event fields needed for trip detection."""
    id: int
    gps_datetime: datetime
    ignition: bool | None
    latitude: float | None
    longitude: float | None
    distance: float | None  # cumulative odometer from device (km)
    speed: float | None     # GPS speed from device (km/h)
    packet_type: str | None = None


@dataclass
class OpenTrip:
    """Mutable in-memory state of a trip still in progress.
    Serialised into / restored from DB between detector runs.
    """
    trip_id: uuid.UUID
    vehicle_reg_no: str | None
    imei: str
    start_event_id: int
    started_at: datetime
    start_lat: float | None
    start_lon: float | None
    last_event_id: int
    last_event_at: datetime
    last_lat: float | None
    last_lon: float | None
    last_odometer_km: float | None          # last valid odometer reading
    accumulated_distance_km: float = field(default=0.0)
    # Speed accumulators — updated on every event with valid speed
    max_speed_kmph: float | None = field(default=None)
    min_speed_kmph: float | None = field(default=None)
    # Day/Night accumulators — night = 20:00–05:00
    day_distance_km: float = field(default=0.0)
    night_distance_km: float = field(default=0.0)
    day_duration_seconds: float = field(default=0.0)
    night_duration_seconds: float = field(default=0.0)
    harsh_acceleration_count: int = 0
    harsh_braking_count: int = 0
    harsh_turning_count: int = 0


@dataclass(frozen=True)
class OpenTripAction:
    """A new trip has started — persist a new vehicle_trips row."""
    trip: OpenTrip


@dataclass(frozen=True)
class CloseTripAction:
    """A trip has ended — update the vehicle_trips row to closed."""
    trip_id: uuid.UUID
    end_event_id: int
    ended_at: datetime
    end_lat: float | None
    end_lon: float | None
    total_distance_km: float
    total_duration_seconds: int
    max_speed_kmph: float | None
    min_speed_kmph: float | None
    avg_speed_kmph: float | None
    day_distance_km: float
    night_distance_km: float
    day_duration_seconds: int
    night_duration_seconds: int
    harsh_acceleration_count: int
    harsh_braking_count: int
    harsh_turning_count: int


TripAction = OpenTripAction | CloseTripAction
