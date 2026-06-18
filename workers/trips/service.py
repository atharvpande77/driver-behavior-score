from __future__ import annotations

import logging

from workers.trips.detector import TripDetector
from workers.trips.repository import TripRepository
from workers.types import CloseTripAction, OpenTripAction


logger = logging.getLogger(__name__)


class TripService:
    def __init__(self, repo: TripRepository) -> None:
        self.repo = repo

    async def fetch_devices_with_new_events(self) -> list[str]:
        return await self.repo.fetch_devices_with_new_events()

    async def timeout_close_stale_open_trips(self) -> int:
        return await self.repo.timeout_close_stale_open_trips()

    async def run_detector_for_device(self, imei: str) -> None:
        async with self.repo.pool.acquire() as conn:
            await self.repo.ensure_cursor_exists(conn, imei)

            cursor = await self.repo.get_cursor(conn, imei)
            after_id: int = cursor["last_processed_event_id"]

            vehicle_reg_no = await self.repo.fetch_vehicle_reg_no_for_imei(conn, imei)

            open_trip = None
            if cursor["open_trip_id"] is not None:
                open_trip = await self.repo.fetch_open_trip(
                    conn,
                    trip_id=cursor["open_trip_id"],
                    last_event_id=cursor["last_processed_event_id"],
                    last_odometer_km=cursor["last_odometer_km"],
                    vehicle_reg_no=vehicle_reg_no,
                )

            events = await self.repo.fetch_new_events(conn, imei, after_id)
            if not events:
                return

            actions, updated_open_trip = TripDetector.detect_trips(vehicle_reg_no, imei, events, open_trip)

            async with conn.transaction():
                for action in actions:
                    if isinstance(action, OpenTripAction):
                        await self.repo.insert_trip(conn, action)
                    elif isinstance(action, CloseTripAction):
                        await self.repo.close_trip(conn, action)

                if updated_open_trip is not None:
                    await self.repo.update_open_trip(conn, updated_open_trip)

                await self.repo.update_cursor(
                    conn,
                    imei=imei,
                    last_event_id=events[-1].id,
                    open_trip_id=(
                        updated_open_trip.trip_id if updated_open_trip else None
                    ),
                    last_odometer_km=(
                        updated_open_trip.last_odometer_km if updated_open_trip else None
                    ),
                )

            logger.debug(
                "IMEI %s: processed %d events, %d actions, open=%s",
                imei,
                len(events),
                len(actions),
                updated_open_trip is not None,
            )
