from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from fastapi import Request

from src.auth.types import AuthType
from src.logging_utils import get_logger, log_event
from src.score.types import RiskLevel
from src.types import APINames
from src.usage.repository import UsageEventRepository
from src.usage.schemas import (
    UsageApiKeyStatsResponse,
    UsageRecentVehicleResponse,
    UsageSummaryResponse,
    UsageWindowSummaryResponse,
)
from src.usage.types import UsageEventRequestContext, UsageStatus, UsageType


class UsageEventService:
    SUMMARY_API_NAMES: tuple[str, ...] = (
        APINames.DASHBOARD_SINGLE_VEHICLE_LOOKUP.value,
        APINames.DASHBOARD_BATCH_VEHICLE_LOOKUP.value,
        APINames.SCORE.value,
        APINames.VIOLATIONS.value,
        APINames.VEHICLES.value,
    )
    API_KEY_API_NAMES: tuple[str, ...] = (
        APINames.SCORE.value,
        APINames.VIOLATIONS.value,
        APINames.VEHICLES.value,
    )
    RISK_CATEGORY_NAMES: tuple[str, ...] = tuple(risk.value for risk in RiskLevel) + ("UNKNOWN",)

    def __init__(
        self,
        *,
        repo: UsageEventRepository,
    ):
        self.repo = repo
        self.logger = get_logger(__name__)

    async def persist_request_usage(
        self,
        *,
        request: Request,
        total_latency_ms: float,
        http_status_code: int,
        error_type: str | None,
    ) -> None:
        if not getattr(request.state, "collect_usage", True):
            return

        stats_per_vehicle = list(getattr(request.state, "stats_per_vehicle", []))
        if not stats_per_vehicle:
            return

        auth_type = getattr(request.state, "auth_type", None)
        dashboard_user_id = getattr(request.state, "dashboard_user_id", None)

        if auth_type is None or dashboard_user_id is None:
            log_event(
                self.logger,
                "INFO",
                "usage.persist.skip_missing_auth_context",
                path=request.url.path,
                has_stats=bool(stats_per_vehicle),
                auth_type=str(auth_type) if auth_type is not None else None,
                dashboard_user_id=str(dashboard_user_id) if dashboard_user_id is not None else None,
            )
            return

        api_key_id = getattr(request.state, "api_key_id", None)
        request_context = UsageEventRequestContext(
            request_id=self._coerce_request_id(getattr(request.state, "request_id", None)),
            dashboard_user_id=dashboard_user_id,
            api_key_id=api_key_id,
            auth_type=self._normalize_auth_type(auth_type),
            endpoint=request.url.path,
            method=request.method,
            usage_type=self._resolve_usage_type(stats_per_vehicle),
            total_latency_ms=total_latency_ms,
            is_success=http_status_code < 400,
            status=UsageStatus.SUCCESS if http_status_code < 400 else UsageStatus.ERROR,
            error_type=error_type,
            http_status_code=http_status_code,
            ip_address=self._get_ip_address(request),
            user_agent=request.headers.get("user-agent"),
        )

        rows = self._build_rows(request_context, stats_per_vehicle)
        if not rows:
            return

        try:
            await self.repo.insert_many(rows)
            await self.repo.commit()
        except Exception:
            await self.repo.rollback()
            log_event(
                self.logger,
                "ERROR",
                "usage.persist.failed",
                path=request_context.endpoint,
                method=request_context.method,
                http_status_code=http_status_code,
                row_count=len(rows),
            )
            self.logger.exception("event=usage.persist.failed path=%s method=%s", request_context.endpoint, request_context.method)

    async def get_recent_vehicle_queries(self, dashboard_user_id: UUID) -> list[UsageRecentVehicleResponse]:
        rows = await self.repo.get_recent_vehicle_queries(
            dashboard_user_id,
            api_names=list(self.SUMMARY_API_NAMES[:2]),
        )
        return [
            UsageRecentVehicleResponse(
                vehicle_number=row["vehicle_number"],
                risk_category=row["risk_level"],
                queried_at=row["queried_at"],
            )
            for row in rows
        ]

    async def get_usage_summary(self, dashboard_user_id: UUID) -> UsageSummaryResponse:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_seven_days_start = now - timedelta(days=7)

        return UsageSummaryResponse(
            today=await self._build_window_summary(dashboard_user_id, today_start, now),
            last_seven_days=await self._build_window_summary(dashboard_user_id, last_seven_days_start, now),
            current_month=await self._build_window_summary(dashboard_user_id, month_start, now),
        )

    async def get_api_key_usage(self, dashboard_user_id: UUID) -> list[UsageApiKeyStatsResponse]:
        owned_keys = await self.repo.list_owned_api_keys(dashboard_user_id)
        usage_counts = await self.repo.get_api_key_request_counts(
            dashboard_user_id,
            api_names=list(self.API_KEY_API_NAMES),
        )

        counts_by_key: dict[UUID, dict[str, int]] = {}
        totals_by_key: dict[UUID, int] = {}
        for row in usage_counts:
            api_key_id = row["api_key_id"]
            api_name = row["api_name"]
            request_count = int(row["request_count"] or 0)
            counts_by_key.setdefault(api_key_id, self._zero_count_map(self.API_KEY_API_NAMES))
            counts_by_key[api_key_id][api_name] = request_count
            totals_by_key[api_key_id] = totals_by_key.get(api_key_id, 0) + request_count

        return [
            UsageApiKeyStatsResponse(
                id=row["id"],
                name=row["name"],
                key_prefix=row["key_prefix"],
                is_active=row["is_active"],
                created_at=row.get("created_at"),
                last_used_at=row.get("last_used_at"),
                total_requests=totals_by_key.get(row["id"], 0),
                requests_by_api=self._zero_count_map(self.API_KEY_API_NAMES, counts_by_key.get(row["id"], {})),
            )
            for row in owned_keys
        ]

    def _build_rows(
        self,
        request_context: UsageEventRequestContext,
        stats_per_vehicle: list[Mapping[str, object]],
    ) -> list[dict]:
        rows: list[dict] = []
        for stat in stats_per_vehicle:
            api_name = self._normalize_api_name(stat.get("api_name"))
            vehicle_number = stat.get("vehicle_number")
            risk_level = stat.get("risk_category") or "UNKNOWN"

            if not vehicle_number:
                continue

            rows.append(
                {
                    "request_id": request_context.request_id,
                    "dashboard_user_id": request_context.dashboard_user_id,
                    "api_key_id": request_context.api_key_id,
                    "auth_type": request_context.auth_type,
                    "endpoint": request_context.endpoint,
                    "method": request_context.method,
                    "api_name": api_name,
                    "usage_type": request_context.usage_type.value,
                    "vehicle_number": vehicle_number,
                    "risk_level": risk_level,
                    "from_db_cache": bool(stat.get("from_db_cache", False)),
                    "challan_net_changes": int(stat.get("challan_net_changes") or 0),
                    "total_latency_ms": request_context.total_latency_ms,
                    "vendor_challan_latency_ms": stat.get("vendor_challan_latency_ms"),
                    "vendor_rc_latency_ms": stat.get("vendor_rc_latency_ms"),
                    "is_success": request_context.is_success,
                    "status": request_context.status.value,
                    "error_type": request_context.error_type,
                    "http_status_code": request_context.http_status_code,
                    "ip_address": request_context.ip_address,
                    "user_agent": request_context.user_agent,
                }
            )

        return rows

    def _resolve_usage_type(self, stats_per_vehicle: list[Mapping[str, object]]) -> UsageType:
        if len(stats_per_vehicle) > 1:
            return UsageType.BATCH

        api_name = self._normalize_api_name(stats_per_vehicle[0].get("api_name"))
        if api_name == APINames.DASHBOARD_BATCH_VEHICLE_LOOKUP.value:
            return UsageType.BATCH
        return UsageType.SINGLE

    def _normalize_api_name(self, value: object) -> str:
        if isinstance(value, APINames):
            return value.value
        return str(value) if value is not None else ""

    def _normalize_auth_type(self, value: object) -> str:
        if isinstance(value, AuthType):
            return value.value
        return str(value)

    def _coerce_request_id(self, value: object) -> UUID:
        if isinstance(value, UUID):
            return value
        if value is None:
            return uuid4()
        value_str = str(value)
        try:
            return UUID(value_str)
        except ValueError:
            return uuid5(NAMESPACE_URL, value_str)

    def _get_ip_address(self, request: Request) -> str | None:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip() or None

        client = request.client
        if client is None:
            return None
        return client.host

    async def _build_window_summary(
        self,
        dashboard_user_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> UsageWindowSummaryResponse:
        counts = await self.repo.get_window_counts(
            dashboard_user_id,
            start_at=start_at,
            end_at=end_at,
        )
        return UsageWindowSummaryResponse(
            total_requests=int(counts["total_requests"]),
            total_unique_vehicles=int(counts["total_unique_vehicles"]),
            requests_by_api=self._zero_count_map(self.SUMMARY_API_NAMES, counts.get("requests_by_api", {})),
            risk_category_counts=self._zero_count_map(self.RISK_CATEGORY_NAMES, counts.get("risk_category_counts", {})),
        )

    def _zero_count_map(
        self,
        ordered_keys: Sequence[str],
        existing_counts: Mapping[str, int] | None = None,
    ) -> dict[str, int]:
        counts: dict[str, int] = {key: 0 for key in ordered_keys}
        if existing_counts:
            for key, value in existing_counts.items():
                counts[str(key)] = int(value or 0)
        for key in ordered_keys:
            counts.setdefault(key, 0)
        return counts
