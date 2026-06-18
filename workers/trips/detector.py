from __future__ import annotations

from datetime import datetime, timedelta

from workers.types import (
    CloseTripAction,
    EventRow,
    OpenTrip,
    OpenTripAction,
    TripAction,
)
from workers.trips.constants import (
    GAP_THRESHOLD_SECONDS,
    MIN_SPEED_THRESHOLD_KMPH,
    NIGHT_END_HOUR,
    NIGHT_START_HOUR,
)
from workers.trips.utils import is_night, new_open_trip, segment_distance


class TripDetector:
    @classmethod
    def _day_night_split(
        cls,
        start: datetime,
        end: datetime,
        distance_km: float,
    ) -> tuple[float, float, float, float]:
        """Proportionally split a driving segment into day and night portions.

        Night is 20:00–05:00 (fixed clock time, no timezone conversion).
        Distance is split linearly by duration.

        Returns:
            (day_distance_km, night_distance_km, day_seconds, night_seconds)
        """
        total_seconds = (end - start).total_seconds()
        if total_seconds <= 0:
            return 0.0, 0.0, 0.0, 0.0

        # Collect all 05:00 / 20:00 boundary crossings within [start, end].
        boundaries: list[datetime] = [start]
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= end:
            for hour in (NIGHT_END_HOUR, NIGHT_START_HOUR):
                b = day.replace(hour=hour)
                if start < b < end:
                    boundaries.append(b)
            day += timedelta(days=1)
        boundaries.append(end)
        boundaries.sort()

        day_s = night_s = 0.0
        for i in range(len(boundaries) - 1):
            seg_start = boundaries[i]
            seg_end = boundaries[i + 1]
            seg_s = (seg_end - seg_start).total_seconds()
            # Classify by the midpoint hour.
            mid = seg_start + (seg_end - seg_start) / 2
            if is_night(mid.hour):
                night_s += seg_s
            else:
                day_s += seg_s

        ratio = distance_km / total_seconds
        return day_s * ratio, night_s * ratio, day_s, night_s

    @classmethod
    def _accumulate_speed(cls, trip: OpenTrip, speed: float | None) -> None:
        """Update in-place max/min speed stats on the open trip.

        max_speed considers any non-negative reading.
        min_speed only considers readings >= MIN_SPEED_THRESHOLD_KMPH so that
        near-zero idle/noise values don't pollute the minimum.
        """
        if speed is None or speed < 0:
            return
        if trip.max_speed_kmph is None or speed > trip.max_speed_kmph:
            trip.max_speed_kmph = speed
        if speed >= MIN_SPEED_THRESHOLD_KMPH:
            if trip.min_speed_kmph is None or speed < trip.min_speed_kmph:
                trip.min_speed_kmph = speed

    @classmethod
    def _accumulate_harsh_events(cls, trip: OpenTrip, packet_type: str | None) -> None:
        if packet_type == "HA":
            trip.harsh_acceleration_count += 1
        elif packet_type == "HB":
            trip.harsh_braking_count += 1
        elif packet_type == "RT":
            trip.harsh_turning_count += 1

    @classmethod
    def _close_trip(
        cls,
        trip: OpenTrip,
        end_event_id: int,
        ended_at: datetime,
        end_lat: float | None,
        end_lon: float | None,
        distance_km: float,
    ) -> CloseTripAction:
        duration_s = max(0, int((ended_at - trip.started_at).total_seconds()))
        duration_h = duration_s / 3600
        avg = round(distance_km / duration_h, 2) if duration_h > 0 else None
        return CloseTripAction(
            trip_id=trip.trip_id,
            end_event_id=end_event_id,
            ended_at=ended_at,
            end_lat=end_lat,
            end_lon=end_lon,
            total_distance_km=distance_km,
            total_duration_seconds=duration_s,
            max_speed_kmph=trip.max_speed_kmph,
            min_speed_kmph=trip.min_speed_kmph,
            avg_speed_kmph=avg,
            day_distance_km=round(trip.day_distance_km, 4),
            night_distance_km=round(trip.night_distance_km, 4),
            day_duration_seconds=int(trip.day_duration_seconds),
            night_duration_seconds=int(trip.night_duration_seconds),
            harsh_acceleration_count=trip.harsh_acceleration_count,
            harsh_braking_count=trip.harsh_braking_count,
            harsh_turning_count=trip.harsh_turning_count,
        )

    @classmethod
    def detect_trips(
        cls,
        vehicle_reg_no: str | None,
        imei: str,
        events: list[EventRow],
        open_trip: OpenTrip | None,
    ) -> tuple[list[TripAction], OpenTrip | None]:
        """Process a time-ordered list of DP events for one vehicle.

        Returns:
            actions  — ordered list of OpenTripAction / CloseTripAction to persist.
            open_trip — updated OpenTrip if a trip is still running after processing
                        all events, else None. The caller persists its live state.
        """
        actions: list[TripAction] = []

        for event in events:
            ignition = event.ignition

            if open_trip is not None:
                gap = (event.gps_datetime - open_trip.last_event_at).total_seconds()

                # Drop out-of-order / reversed events.
                if gap < 0:
                    continue

                if gap > GAP_THRESHOLD_SECONDS:
                    # Safety net: device went silent for >30 min — close at the last
                    # known event. This complements timeout_close_stale_open_trips()
                    # which handles the case where no new events arrive at all.
                    actions.append(cls._close_trip(
                        open_trip,
                        end_event_id=open_trip.last_event_id,
                        ended_at=open_trip.last_event_at,
                        end_lat=open_trip.last_lat,
                        end_lon=open_trip.last_lon,
                        distance_km=open_trip.accumulated_distance_km,
                    ))
                    open_trip = None

                    # Resume strict ignition logic for the current event.
                    if ignition is True:
                        open_trip = new_open_trip(vehicle_reg_no, imei, event)
                        cls._accumulate_speed(open_trip, event.speed)
                        cls._accumulate_harsh_events(open_trip, event.packet_type)
                        actions.append(OpenTripAction(trip=open_trip))
                    # ignition=False or None after a gap → parked, skip.

                elif ignition is False:
                    # ignition=False → end of trip (0,1,1,...,0 pattern).
                    seg = segment_distance(
                        open_trip.last_odometer_km, event.distance,
                        open_trip.last_lat, open_trip.last_lon,
                        event.latitude, event.longitude,
                    )
                    d_day, d_night, s_day, s_night = cls._day_night_split(
                        open_trip.last_event_at, event.gps_datetime, seg
                    )
                    open_trip.day_distance_km += d_day
                    open_trip.night_distance_km += d_night
                    open_trip.day_duration_seconds += s_day
                    open_trip.night_duration_seconds += s_night
                    cls._accumulate_speed(open_trip, event.speed)
                    cls._accumulate_harsh_events(open_trip, event.packet_type)
                    actions.append(cls._close_trip(
                        open_trip,
                        end_event_id=event.id,
                        ended_at=event.gps_datetime,
                        end_lat=event.latitude,
                        end_lon=event.longitude,
                        distance_km=open_trip.accumulated_distance_km + seg,
                    ))
                    open_trip = None

                else:
                    # ignition=True or None — still driving, accumulate.
                    seg = segment_distance(
                        open_trip.last_odometer_km, event.distance,
                        open_trip.last_lat, open_trip.last_lon,
                        event.latitude, event.longitude,
                    )
                    d_day, d_night, s_day, s_night = cls._day_night_split(
                        open_trip.last_event_at, event.gps_datetime, seg
                    )
                    open_trip.accumulated_distance_km += seg
                    open_trip.day_distance_km += d_day
                    open_trip.night_distance_km += d_night
                    open_trip.day_duration_seconds += s_day
                    open_trip.night_duration_seconds += s_night
                    open_trip.last_event_id = event.id
                    open_trip.last_event_at = event.gps_datetime
                    open_trip.last_lat = event.latitude
                    open_trip.last_lon = event.longitude
                    if event.distance is not None:
                        open_trip.last_odometer_km = event.distance
                    cls._accumulate_speed(open_trip, event.speed)
                    cls._accumulate_harsh_events(open_trip, event.packet_type)

            else:
                # No open trip — only ignition=True starts one.
                if ignition is True:
                    open_trip = new_open_trip(vehicle_reg_no, imei, event)
                    cls._accumulate_speed(open_trip, event.speed)
                    cls._accumulate_harsh_events(open_trip, event.packet_type)
                    actions.append(OpenTripAction(trip=open_trip))
                # ignition=False with no open trip = parked → skip

        return actions, open_trip
