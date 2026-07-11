import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.core.database import BaseDBRepository
from src.core.models import TelematicsDevice, VehicleTrip
from src.telematics.types import PaginationParams


class TelematicsRepository(BaseDBRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db)

    # ── Devices ──────────────────────────────────────────────────────────────

    async def count_devices(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(TelematicsDevice))
        return result.scalar_one()

    async def list_devices(self, params: PaginationParams) -> list[TelematicsDevice]:
        result = await self.db.execute(
            select(TelematicsDevice)
            .order_by(TelematicsDevice.last_seen_at.desc().nulls_last())
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(result.scalars().all())

    # ── Trips ─────────────────────────────────────────────────────────────────

    async def get_active_trip_for_vehicle(self, vehicle_reg_no: str) -> VehicleTrip | None:
        """Return the single open trip for this vehicle, or None."""
        result = await self.db.execute(
            select(VehicleTrip)
            .where(
                VehicleTrip.vehicle_reg_no == vehicle_reg_no,
                VehicleTrip.status == "open",
                VehicleTrip.total_distance_km != 0,
            )
            .limit(1)
        )
        return result.scalars().first()

    async def get_recent_closed_trips_for_vehicle(
        self, vehicle_reg_no: str, limit: int = 10
    ) -> list[VehicleTrip]:
        """Return the most recent closed trips (up to `limit`), newest first."""
        result = await self.db.execute(
            select(VehicleTrip)
            .where(
                VehicleTrip.vehicle_reg_no == vehicle_reg_no,
                VehicleTrip.status == "closed",
                VehicleTrip.total_distance_km != 0,
            )
            .order_by(VehicleTrip.started_at.desc().nulls_last())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_vehicle_stats(
        self, vehicle_reg_no: str, start_dt: datetime, end_dt: datetime
    ):
        """
        Single aggregation query: COUNT, SUM, MAX, MIN across all closed,
        non-zero-distance trips within the [start_dt, end_dt] window.
        Returns a single Row (all cols are 0 / 0.0 when no trips match).
        """
        result = await self.db.execute(
            select(
                func.count().label("trips_included"),
                func.coalesce(func.sum(VehicleTrip.total_distance_km), 0.0).label("total_km"),
                func.coalesce(func.max(VehicleTrip.total_distance_km), 0.0).label("longest_trip_km"),
                func.coalesce(func.min(VehicleTrip.total_distance_km), 0.0).label("shortest_trip_km"),
                func.coalesce(func.sum(VehicleTrip.day_distance_km), 0.0).label("day_km"),
                func.coalesce(func.sum(VehicleTrip.night_distance_km), 0.0).label("night_km"),
                func.coalesce(func.sum(VehicleTrip.total_duration_seconds), 0).label("total_seconds"),
                func.coalesce(func.max(VehicleTrip.total_duration_seconds), 0).label("longest_trip_seconds"),
                func.coalesce(func.sum(VehicleTrip.day_duration_seconds), 0).label("day_seconds"),
                func.coalesce(func.sum(VehicleTrip.night_duration_seconds), 0).label("night_seconds"),
                func.coalesce(func.max(VehicleTrip.max_speed_kmph), 0.0).label("max_kmph"),
                func.coalesce(func.sum(VehicleTrip.harsh_acceleration_count), 0).label("harsh_acceleration"),
                func.coalesce(func.sum(VehicleTrip.harsh_braking_count), 0).label("harsh_braking"),
                func.coalesce(func.sum(VehicleTrip.harsh_turning_count), 0).label("harsh_turning"),
            )
            .select_from(VehicleTrip)
            .where(
                VehicleTrip.vehicle_reg_no == vehicle_reg_no,
                VehicleTrip.status == "closed",
                VehicleTrip.total_distance_km != 0,
                VehicleTrip.started_at >= start_dt,
                VehicleTrip.started_at <= end_dt,
            )
        )
        return result.one()
