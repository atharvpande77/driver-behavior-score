from collections.abc import Iterable
from datetime import datetime, timezone
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
        start_at = start_at.astimezone(timezone.utc).replace(tzinfo=None)
        end_at = end_at.astimezone(timezone.utc).replace(tzinfo=None)
        created_at_utc = func.timezone("UTC", UsageEvent.created_at)
        filters = (
            UsageEvent.dashboard_user_id == dashboard_user_id,
            created_at_utc >= start_at,
            created_at_utc < end_at,
        )

        totals_result = await self.db.execute(
            select(
                func.count(distinct(UsageEvent.request_id)).label("total_requests"),
                func.count(distinct(UsageEvent.request_id)).filter(UsageEvent.is_success.is_(True)).label("successful_requests"),
                func.count(distinct(UsageEvent.request_id)).filter(UsageEvent.is_success.is_(False)).label("failed_requests"),
            ).where(*filters)
        )
        totals = totals_result.mappings().one()

        return {
            "total_requests": int(totals["total_requests"] or 0),
            "successful_requests": int(totals["successful_requests"] or 0),
            "failed_requests": int(totals["failed_requests"] or 0),
        }

    async def get_time_series_counts(
        self,
        dashboard_user_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
        granularity: str,
    ) -> list[dict]:
        start_at = start_at.astimezone(timezone.utc).replace(tzinfo=None)
        end_at = end_at.astimezone(timezone.utc).replace(tzinfo=None)
        created_at_utc = func.timezone("UTC", UsageEvent.created_at)
        bucket_start = func.date_trunc(granularity, created_at_utc).label("period_start")
        result = await self.db.execute(
            select(
                bucket_start,
                UsageEvent.is_success.label("is_success"),
                func.count(distinct(UsageEvent.request_id)).label("request_count"),
            )
            .where(
                UsageEvent.dashboard_user_id == dashboard_user_id,
                created_at_utc >= start_at,
                created_at_utc < end_at,
            )
            .group_by(bucket_start, UsageEvent.is_success)
            .order_by(bucket_start.asc())
        )
        return list(result.mappings().all())

    async def get_risk_distribution(
        self,
        dashboard_user_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
        api_names: list[str],
    ) -> list[dict]:
        start_at = start_at.astimezone(timezone.utc).replace(tzinfo=None)
        end_at = end_at.astimezone(timezone.utc).replace(tzinfo=None)
        created_at_utc = func.timezone("UTC", UsageEvent.created_at)
        result = await self.db.execute(
            select(
                UsageEvent.risk_level.label("risk_level"),
                func.count().label("request_count"),
            )
            .where(
                UsageEvent.dashboard_user_id == dashboard_user_id,
                created_at_utc >= start_at,
                created_at_utc < end_at,
                UsageEvent.api_name.in_(api_names),
            )
            .group_by(UsageEvent.risk_level)
        )
        return list(result.mappings().all())

    async def get_last_request_timestamp(self, dashboard_user_id: UUID) -> datetime | None:
        result = await self.db.execute(
            select(func.max(UsageEvent.created_at)).where(
                UsageEvent.dashboard_user_id == dashboard_user_id,
            )
        )
        return result.scalar_one_or_none()

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

    async def get_api_key_usage_counts(
        self,
        dashboard_user_id: UUID,
        *,
        api_names: list[str] | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                UsageEvent.api_key_id.label("api_key_id"),
                UsageEvent.api_name.label("api_name"),
                UsageEvent.is_success.label("is_success"),
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
            stmt.group_by(UsageEvent.api_key_id, UsageEvent.api_name, UsageEvent.is_success)
        )
        return list(result.mappings().all())
