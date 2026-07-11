from datetime import date, datetime, timedelta
from fastapi import HTTPException, status

from src.telematics.repository import TelematicsRepository
from src.telematics.types import PaginationParams, DateRangePreset, ResolvedDateRange
from src.core.logging_utils import get_logger, log_event


def _resolve_date_range(
    range_preset: str | None,
    from_date: date | None,
    to_date: date | None,
) -> ResolvedDateRange:
    """
    Validates parameter combinations and resolves them into concrete
    start/end datetimes in UTC. Raises HTTP 400 on any invalid combination.
    """
    has_preset = range_preset is not None
    has_from   = from_date is not None
    has_to     = to_date is not None

    if has_preset and (has_from or has_to):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'range' or 'from'/'to', not both."
        )
    if not has_preset and not (has_from and has_to):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 'range', or both 'from' and 'to'."
        )
    if has_from and has_to and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'from' must not be later than 'to'."
        )

    today = date.today()

    if has_preset:
        try:
            preset = DateRangePreset(range_preset)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid 'range' value. Allowed: {[p.value for p in DateRangePreset]}",
            )
        if preset == DateRangePreset.TODAY:
            resolved_from = today
        elif preset == DateRangePreset.LAST_7_DAYS:
            resolved_from = today - timedelta(days=6)
        else:  # LAST_30_DAYS
            resolved_from = today - timedelta(days=29)
        resolved_to = today
        label = preset.value
    else:
        resolved_from = from_date
        resolved_to   = to_date
        label         = None

    return ResolvedDateRange(
        start_dt   = datetime(resolved_from.year, resolved_from.month, resolved_from.day, 0, 0, 0),
        end_dt     = datetime(resolved_to.year,   resolved_to.month,   resolved_to.day,   23, 59, 59),
        range_label = label,
        from_date  = resolved_from,
        to_date    = resolved_to,
    )


class TelematicsService:
    def __init__(self, *, repo: TelematicsRepository):
        self.repo = repo
        self.logger = get_logger(__name__)

    async def list_devices(self, params: PaginationParams):
        log_event(self.logger, "INFO", "telematics.devices.list", page=params.page, limit=params.limit)
        total = await self.repo.count_devices()
        items = await self.repo.list_devices(params)
        return items, total

    async def get_vehicle_trips(self, vehicle_reg_no: str):
        log_event(self.logger, "INFO", "telematics.trips.get", vehicle_reg_no=vehicle_reg_no)
        active_trip = await self.repo.get_active_trip_for_vehicle(vehicle_reg_no)
        recent_trips = await self.repo.get_recent_closed_trips_for_vehicle(vehicle_reg_no)
        return active_trip, recent_trips

    async def get_vehicle_stats(
        self,
        vehicle_reg_no: str,
        range_preset: str | None,
        from_date: date | None,
        to_date: date | None,
    ) -> dict:
        dr = _resolve_date_range(range_preset, from_date, to_date)
        log_event(
            self.logger,
            "INFO",
            "telematics.stats.get",
            vehicle_reg_no=vehicle_reg_no,
            from_date=str(dr.from_date),
            to_date=str(dr.to_date)
        )

        row = await self.repo.get_vehicle_stats(vehicle_reg_no, dr.start_dt, dr.end_dt)

        trips     = row.trips_included
        total_km  = float(row.total_km)
        total_sec = int(row.total_seconds)

        # Derived distance metrics
        avg_per_trip_km = round(total_km / trips, 2) if trips else 0.0
        night_km        = float(row.night_km)
        night_pct       = round((night_km / total_km) * 100, 1) if total_km else 0.0

        # Derived duration metrics
        avg_per_trip_sec = round(total_sec / trips) if trips else 0

        # Derived speed
        avg_kmph = round(total_km * 3600 / total_sec, 1) if total_sec else 0.0

        # Safety
        harsh_acc   = int(row.harsh_acceleration)
        harsh_brk   = int(row.harsh_braking)
        harsh_trn   = int(row.harsh_turning)
        total_harsh = harsh_acc + harsh_brk + harsh_trn
        harsh_per_100 = round(total_harsh / (total_km / 100), 1) if total_km else 0.0

        return {
            "vehicle_reg_no": vehicle_reg_no,
            "range":           dr.range_label,
            "from_date":       dr.from_date,
            "to_date":         dr.to_date,
            "trips_included":  trips,
            "distance": {
                "total_km":         round(total_km, 1),
                "avg_per_trip_km":  avg_per_trip_km,
                "longest_trip_km":  round(float(row.longest_trip_km), 1),
                "shortest_trip_km": round(float(row.shortest_trip_km), 1),
                "day_km":           round(float(row.day_km), 1),
                "night_km":         round(night_km, 1),
                "night_pct":        night_pct,
            },
            "duration": {
                "total_seconds":       total_sec,
                "avg_per_trip_seconds": avg_per_trip_sec,
                "longest_trip_seconds": int(row.longest_trip_seconds),
                "day_seconds":          int(row.day_seconds),
                "night_seconds":        int(row.night_seconds),
            },
            "speed": {
                "max_kmph": round(float(row.max_kmph), 1),
                "avg_kmph": avg_kmph,
            },
            "safety": {
                "harsh_acceleration":    harsh_acc,
                "harsh_braking":         harsh_brk,
                "harsh_turning":         harsh_trn,
                "total_harsh_events":    total_harsh,
                "harsh_events_per_100km": harsh_per_100,
            },
        }
