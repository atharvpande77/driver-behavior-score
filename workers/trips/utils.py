import uuid

from workers.trips.constants import (
    NIGHT_END_HOUR,
    NIGHT_START_HOUR,
    ODOMETER_RESET_THRESHOLD_KM,
    ODOMETER_NOISE_THRESHOLD_KM,
)
from workers.types import EventRow, OpenTrip
from workers.utils import haversine_km


def is_night(hour: int) -> bool:
    """Check if the given hour falls within the defined night window."""
    return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR


def segment_distance(
    prev_odometer: float | None,
    curr_odometer: float | None,
    prev_lat: float | None,
    prev_lon: float | None,
    curr_lat: float | None,
    curr_lon: float | None,
) -> float:
    """Distance (km) for one GPS ping-to-ping segment.
    Prefers odometer delta; falls back to haversine on reset or missing data.
    """
    if prev_odometer is not None and curr_odometer is not None:
        delta = curr_odometer - prev_odometer
        if 0.0 <= delta <= ODOMETER_RESET_THRESHOLD_KM:
            return delta
        elif delta < 0.0:
            return 0.0
    return haversine_km(prev_lat, prev_lon, curr_lat, curr_lon)



def new_open_trip(vehicle_reg_no: str | None, imei: str, event: EventRow) -> OpenTrip:
    return OpenTrip(
        trip_id=uuid.uuid4(),
        vehicle_reg_no=vehicle_reg_no,
        imei=imei,
        start_event_id=event.id,
        started_at=event.gps_datetime,
        start_lat=event.latitude,
        start_lon=event.longitude,
        last_event_id=event.id,
        last_event_at=event.gps_datetime,
        last_lat=event.latitude,
        last_lon=event.longitude,
        last_odometer_km=event.distance,
        accumulated_distance_km=0.0,
    )
