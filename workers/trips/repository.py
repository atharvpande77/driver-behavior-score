from __future__ import annotations

import logging
import uuid

import asyncpg

from workers.types import CloseTripAction, EventRow, OpenTrip, OpenTripAction


logger = logging.getLogger(__name__)

_FETCH_LIMIT = 2000


class TripRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def fetch_devices_with_new_events(self) -> list[str]:
        rows = await self.pool.fetch("""
            SELECT DISTINCT te.imei
            FROM telematics_events te
            LEFT JOIN telematics_trip_cursor c ON c.imei = te.imei
            WHERE te.header = 'DP'
              AND te.imei IS NOT NULL
              AND te.id > COALESCE(c.last_processed_event_id, 0)
        """)
        return [row["imei"] for row in rows]

    async def fetch_vehicle_reg_no_for_imei(self, conn: asyncpg.Connection, imei: str) -> str | None:
        row = await conn.fetchrow("""
            SELECT vehicle_reg_no
            FROM telematics_events
            WHERE imei = $1
              AND vehicle_reg_no IS NOT NULL
              AND vehicle_reg_no <> 'NA'
            GROUP BY vehicle_reg_no
            ORDER BY count(*) DESC
            LIMIT 1
        """, imei)
        return row["vehicle_reg_no"] if row else None

    async def ensure_cursor_exists(self, conn: asyncpg.Connection, imei: str) -> None:
        await conn.execute("""
            INSERT INTO telematics_trip_cursor (imei, last_processed_event_id)
            VALUES ($1, 0)
            ON CONFLICT (imei) DO NOTHING
        """, imei)

    async def get_cursor(self, conn: asyncpg.Connection, imei: str) -> asyncpg.Record:
        return await conn.fetchrow("""
            SELECT imei, last_processed_event_id, open_trip_id, last_odometer_km
            FROM telematics_trip_cursor
            WHERE imei = $1
        """, imei)

    async def fetch_open_trip(
        self,
        conn: asyncpg.Connection,
        trip_id: uuid.UUID,
        last_event_id: int,
        last_odometer_km: float | None,
        vehicle_reg_no: str,
    ) -> OpenTrip | None:
        row = await conn.fetchrow("""
            SELECT
                id, vehicle_reg_no, imei, start_event_id, started_at,
                start_lat, start_lon,
                ended_at, end_lat, end_lon,
                total_distance_km,
                day_distance_km, night_distance_km,
                day_duration_seconds, night_duration_seconds,
                max_speed_kmph, min_speed_kmph,
                harsh_acceleration_count, harsh_braking_count, harsh_turning_count
            FROM vehicle_trips
            WHERE id = $1
        """, trip_id)
        if row is None:
            return None
        return OpenTrip(
            trip_id=row["id"],
            vehicle_reg_no=row["vehicle_reg_no"],
            imei=row["imei"] or "",
            start_event_id=row["start_event_id"],
            started_at=row["started_at"],
            start_lat=row["start_lat"],
            start_lon=row["start_lon"],
            last_event_id=last_event_id,
            last_event_at=row["ended_at"] or row["started_at"],
            last_lat=row["end_lat"] or row["start_lat"],
            last_lon=row["end_lon"] or row["start_lon"],
            last_odometer_km=last_odometer_km,
            accumulated_distance_km=row["total_distance_km"] or 0.0,
            max_speed_kmph=row["max_speed_kmph"],
            min_speed_kmph=row["min_speed_kmph"],
            day_distance_km=row["day_distance_km"] or 0.0,
            night_distance_km=row["night_distance_km"] or 0.0,
            day_duration_seconds=float(row["day_duration_seconds"] or 0),
            night_duration_seconds=float(row["night_duration_seconds"] or 0),
            harsh_acceleration_count=row["harsh_acceleration_count"] or 0,
            harsh_braking_count=row["harsh_braking_count"] or 0,
            harsh_turning_count=row["harsh_turning_count"] or 0,
        )

    async def fetch_new_events(
        self,
        conn: asyncpg.Connection,
        imei: str,
        after_id: int,
    ) -> list[EventRow]:
        rows = await conn.fetch("""
            SELECT id, gps_datetime, ignition, latitude, longitude, distance, speed, packet_type
            FROM telematics_events
            WHERE imei = $1
              AND header = 'DP'
              AND gps_datetime IS NOT NULL
              AND id > $2
            ORDER BY id ASC
            LIMIT $3
        """, imei, after_id, _FETCH_LIMIT)
        events = [
            EventRow(
                id=row["id"],
                gps_datetime=row["gps_datetime"],
                ignition=row["ignition"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                distance=row["distance"],
                speed=row["speed"],
                packet_type=row["packet_type"],
            )
            for row in rows
        ]
        events.sort(key=lambda e: e.gps_datetime)
        return events

    async def insert_trip(self, conn: asyncpg.Connection, action: OpenTripAction) -> None:
        t = action.trip
        await conn.execute("""
            INSERT INTO vehicle_trips (
                id, vehicle_reg_no, imei, status,
                start_event_id, started_at, start_lat, start_lon,
                ended_at, end_lat, end_lon,
                total_distance_km, total_duration_seconds,
                day_distance_km, night_distance_km,
                day_duration_seconds, night_duration_seconds,
                harsh_acceleration_count, harsh_braking_count, harsh_turning_count
            )
            VALUES ($1, $2, $3, 'open', $4, $5, $6, $7, $5, $6, $7, 0.0, 0, 0.0, 0.0, 0, 0, $8, $9, $10)
        """,
            t.trip_id, t.vehicle_reg_no, t.imei,
            t.start_event_id, t.started_at, t.start_lat, t.start_lon,
            t.harsh_acceleration_count, t.harsh_braking_count, t.harsh_turning_count,
        )

    async def update_open_trip(self, conn: asyncpg.Connection, trip: OpenTrip) -> None:
        dur = max(0, int((trip.last_event_at - trip.started_at).total_seconds()))
        dur_h = dur / 3600
        avg = round(trip.accumulated_distance_km / dur_h, 2) if dur_h > 0 else None
        await conn.execute("""
            UPDATE vehicle_trips
            SET ended_at               = $1,
                end_lat                = $2,
                end_lon                = $3,
                total_distance_km      = $4,
                total_duration_seconds = $5,
                max_speed_kmph         = $6,
                min_speed_kmph         = $7,
                avg_speed_kmph         = $8,
                day_distance_km        = $9,
                night_distance_km      = $10,
                day_duration_seconds   = $11,
                night_duration_seconds = $12,
                harsh_acceleration_count = $13,
                harsh_braking_count    = $14,
                harsh_turning_count    = $15,
                updated_at             = NOW()
            WHERE id = $16
        """,
            trip.last_event_at, trip.last_lat, trip.last_lon,
            trip.accumulated_distance_km, dur,
            trip.max_speed_kmph, trip.min_speed_kmph,
            round(avg, 2) if avg is not None else None,
            round(trip.day_distance_km, 4), round(trip.night_distance_km, 4),
            int(trip.day_duration_seconds), int(trip.night_duration_seconds),
            trip.harsh_acceleration_count, trip.harsh_braking_count, trip.harsh_turning_count,
            trip.trip_id,
        )

    async def close_trip(self, conn: asyncpg.Connection, action: CloseTripAction) -> None:
        await conn.execute("""
            UPDATE vehicle_trips
            SET status                 = 'closed',
                end_event_id           = $1,
                ended_at               = $2,
                end_lat                = $3,
                end_lon                = $4,
                total_distance_km      = $5,
                total_duration_seconds = $6,
                max_speed_kmph         = $7,
                min_speed_kmph         = $8,
                avg_speed_kmph         = $9,
                day_distance_km        = $10,
                night_distance_km      = $11,
                day_duration_seconds   = $12,
                night_duration_seconds = $13,
                harsh_acceleration_count = $14,
                harsh_braking_count    = $15,
                harsh_turning_count    = $16,
                updated_at             = NOW()
            WHERE id = $17
        """,
            action.end_event_id, action.ended_at,
            action.end_lat, action.end_lon,
            action.total_distance_km, action.total_duration_seconds,
            action.max_speed_kmph, action.min_speed_kmph, action.avg_speed_kmph,
            action.day_distance_km, action.night_distance_km,
            action.day_duration_seconds, action.night_duration_seconds,
            action.harsh_acceleration_count, action.harsh_braking_count, action.harsh_turning_count,
            action.trip_id,
        )

    async def update_cursor(
        self,
        conn: asyncpg.Connection,
        imei: str,
        last_event_id: int,
        open_trip_id: uuid.UUID | None,
        last_odometer_km: float | None,
    ) -> None:
        await conn.execute("""
            UPDATE telematics_trip_cursor
            SET last_processed_event_id = $1,
                open_trip_id            = $2,
                last_odometer_km        = $3,
                updated_at              = NOW()
            WHERE imei = $4
        """, last_event_id, open_trip_id, last_odometer_km, imei)

    async def timeout_close_stale_open_trips(self) -> int:
        closed_ids: list[asyncpg.Record] = []
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                closed_ids = await conn.fetch("""
                    UPDATE vehicle_trips
                    SET status     = 'closed',
                        updated_at = NOW()
                    WHERE status = 'open'
                      AND COALESCE(updated_at, created_at) < NOW() - INTERVAL '30 minutes'
                    RETURNING id
                """)

                if closed_ids:
                    trip_ids = [r["id"] for r in closed_ids]
                    await conn.execute("""
                        UPDATE telematics_trip_cursor
                        SET open_trip_id = NULL,
                            updated_at   = NOW()
                        WHERE open_trip_id = ANY($1::uuid[])
                    """, trip_ids)

        count = len(closed_ids)
        if count:
            logger.info("Timeout-closed %d stale open trip(s)", count)
        return count
