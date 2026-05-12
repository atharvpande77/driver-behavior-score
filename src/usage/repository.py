from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import distinct, func, insert, select
from sqlalchemy.sql import over

from src.database import BaseDBRepository
from src.models import APIKey, UsageEvent


class UsageEventRepository(BaseDBRepository):
    async def insert_many(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        if not rows:
            return
        await self.db.execute(insert(UsageEvent), rows)

    async def get_recent_vehicle_queries(
        self,
        dashboard_user_id: UUID,
        *,
        limit: int = 5,
        api_names: list[str] | None = None,
    ) -> list[dict]:
        filters = [UsageEvent.dashboard_user_id == dashboard_user_id]
        if api_names:
            filters.append(UsageEvent.api_name.in_(api_names))

        ranked = (
            select(
                UsageEvent.vehicle_number.label("vehicle_number"),
                UsageEvent.risk_level.label("risk_level"),
                UsageEvent.created_at.label("queried_at"),
                over(
                    func.row_number(),
                    partition_by=UsageEvent.vehicle_number,
                    order_by=(UsageEvent.created_at.desc(), UsageEvent.id.desc()),
                ).label("row_number"),
            )
            .where(*filters)
            .subquery()
        )

        result = await self.db.execute(
            select(
                ranked.c.vehicle_number,
                ranked.c.risk_level,
                ranked.c.queried_at,
            )
            .where(ranked.c.row_number == 1)
            .order_by(ranked.c.queried_at.desc(), ranked.c.vehicle_number.asc())
            .limit(limit)
        )
        return list(result.mappings().all())

    async def get_window_counts(
        self,
        dashboard_user_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> dict:
        filters = (
            UsageEvent.dashboard_user_id == dashboard_user_id,
            UsageEvent.created_at >= start_at,
            UsageEvent.created_at < end_at,
        )

        totals_result = await self.db.execute(
            select(
                func.count(distinct(UsageEvent.request_id)).label("total_requests"),
                func.count(distinct(UsageEvent.vehicle_number)).label("total_unique_vehicles"),
            ).where(*filters)
        )
        totals = totals_result.mappings().one()

        api_result = await self.db.execute(
            select(
                UsageEvent.api_name.label("api_name"),
                func.count(distinct(UsageEvent.request_id)).label("request_count"),
            )
            .where(*filters)
            .group_by(UsageEvent.api_name)
        )

        risk_result = await self.db.execute(
            select(
                UsageEvent.risk_level.label("risk_level"),
                func.count().label("request_count"),
            )
            .where(*filters)
            .group_by(UsageEvent.risk_level)
        )

        return {
            "total_requests": int(totals["total_requests"] or 0),
            "total_unique_vehicles": int(totals["total_unique_vehicles"] or 0),
            "requests_by_api": {
                row["api_name"]: int(row["request_count"] or 0)
                for row in api_result.mappings().all()
            },
            "risk_category_counts": {
                row["risk_level"]: int(row["request_count"] or 0)
                for row in risk_result.mappings().all()
            },
        }

    async def list_owned_api_keys(self, dashboard_user_id: UUID) -> list[dict]:
        result = await self.db.execute(
            select(
                APIKey.id,
                APIKey.name,
                APIKey.key_prefix,
                APIKey.is_active,
                APIKey.created_at,
                APIKey.last_used_at,
            )
            .where(APIKey.created_by == dashboard_user_id)
            .order_by(APIKey.created_at.desc())
        )
        return list(result.mappings().all())

    async def get_api_key_request_counts(
        self,
        dashboard_user_id: UUID,
        *,
        api_names: list[str] | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                UsageEvent.api_key_id.label("api_key_id"),
                UsageEvent.api_name.label("api_name"),
                func.count(distinct(UsageEvent.request_id)).label("request_count"),
            )
            .where(
                UsageEvent.dashboard_user_id == dashboard_user_id,
                UsageEvent.api_key_id.isnot(None),
            )
        )
        if api_names:
            stmt = stmt.where(UsageEvent.api_name.in_(api_names))

        result = await self.db.execute(
            stmt.group_by(UsageEvent.api_key_id, UsageEvent.api_name)
        )
        return list(result.mappings().all())
