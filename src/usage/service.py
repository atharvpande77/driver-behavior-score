from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from fastapi import Request

from src.auth.types import AuthType
from src.logging_utils import get_logger, log_event
from src.score.types import RiskLevel
from src.types import APINames
from src.usage.repository import UsageEventRepository
from src.usage.schemas import (
    UsageApiKeyStatsResponse,
    UsageApiKeyUsageResponse,
    UsageApiRequestCountResponse,
    UsagePeriodSummaryResponse,
    UsageRecentVehicleResponse,
    UsageRequestCountPointResponse,
    UsageRiskCategoryCountResponse,
    UsageSummaryResponse,
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
    SUMMARY_RISK_API_NAMES: tuple[str, ...] = (
        APINames.DASHBOARD_SINGLE_VEHICLE_LOOKUP.value,
        APINames.DASHBOARD_BATCH_VEHICLE_LOOKUP.value,
        APINames.SCORE.value,
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
        last_12_months_start = self._month_start_offset(now, 11)

        current_month_counts = await self.repo.get_window_counts(
            dashboard_user_id,
            start_at=month_start,
            end_at=now,
        )
        last_request_at = await self.repo.get_last_request_timestamp(dashboard_user_id)

        return UsageSummaryResponse(
            request_success_rate_pct=self._success_rate_pct(
                current_month_counts["successful_requests"],
                current_month_counts["total_requests"],
            ),
            total_calls_this_month=current_month_counts["total_requests"],
            total_failed_requests_this_month=current_month_counts["failed_requests"],
            last_request_at=last_request_at,
            today=await self._build_period_summary(
                dashboard_user_id=dashboard_user_id,
                start_at=today_start,
                end_at=now,
                period_label="today",
            ),
            current_month=await self._build_period_summary(
                dashboard_user_id=dashboard_user_id,
                start_at=month_start,
                end_at=now,
                period_label="month-to-date",
                daily_request_counts=await self._build_time_series(
                    dashboard_user_id=dashboard_user_id,
                    start_at=month_start,
                    end_at=now,
                    granularity="day",
                    fill_start=month_start.date(),
                    fill_end=now.date(),
                ),
            ),
            last_12_months=await self._build_period_summary(
                dashboard_user_id=dashboard_user_id,
                start_at=last_12_months_start,
                end_at=now,
                period_label="rolling 12-month",
                monthly_request_counts=await self._build_time_series(
                    dashboard_user_id=dashboard_user_id,
                    start_at=last_12_months_start,
                    end_at=now,
                    granularity="month",
                    fill_start=last_12_months_start.date(),
                    fill_end=month_start.date(),
                ),
            ),
        )

    async def get_api_key_usage(self, dashboard_user_id: UUID) -> UsageApiKeyUsageResponse:
        owned_keys = await self.repo.list_owned_api_keys(dashboard_user_id)
        usage_counts = await self.repo.get_api_key_usage_counts(
            dashboard_user_id,
            api_names=list(self.API_KEY_API_NAMES),
        )

        api_totals = self._zero_nested_request_counts(self.API_KEY_API_NAMES)
        counts_by_key: dict[UUID, dict[str, dict[str, int]]] = {}
        for row in usage_counts:
            api_key_id = row["api_key_id"]
            api_name = row["api_name"]
            is_success = bool(row["is_success"])
            request_count = int(row["request_count"] or 0)
            api_bucket = api_totals[api_name]
            key_bucket = counts_by_key.setdefault(api_key_id, self._zero_nested_request_counts(self.API_KEY_API_NAMES))

            api_bucket["total_requests"] += request_count
            key_bucket[api_name]["total_requests"] += request_count

            if is_success:
                api_bucket["successful_requests"] += request_count
                key_bucket[api_name]["successful_requests"] += request_count
            else:
                api_bucket["failed_requests"] += request_count
                key_bucket[api_name]["failed_requests"] += request_count

        api_key_items: list[UsageApiKeyStatsResponse] = []
        total_requests = 0
        successful_requests = 0
        failed_requests = 0

        for row in owned_keys:
            key_counts = counts_by_key.get(row["id"], self._zero_nested_request_counts(self.API_KEY_API_NAMES))
            key_total = sum(bucket["total_requests"] for bucket in key_counts.values())
            key_success = sum(bucket["successful_requests"] for bucket in key_counts.values())
            key_failed = sum(bucket["failed_requests"] for bucket in key_counts.values())
            total_requests += key_total
            successful_requests += key_success
            failed_requests += key_failed
            api_key_items.append(
                UsageApiKeyStatsResponse(
                    id=row["id"],
                    name=row["name"],
                    key_prefix=row["key_prefix"],
                    is_active=row["is_active"],
                    created_at=row.get("created_at"),
                    last_used_at=row.get("last_used_at"),
                    total_requests=key_total,
                    successful_requests=key_success,
                    failed_requests=key_failed,
                    requests_by_api=self._to_api_request_count_rows(key_counts),
                )
            )

        return UsageApiKeyUsageResponse(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            requests_by_api=self._to_api_request_count_rows(api_totals),
            api_keys=api_key_items,
        )

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

    async def _build_period_summary(
        self,
        *,
        dashboard_user_id: UUID,
        start_at: datetime,
        end_at: datetime,
        period_label: str,
        daily_request_counts: list[UsageRequestCountPointResponse] | None = None,
        monthly_request_counts: list[UsageRequestCountPointResponse] | None = None,
    ) -> UsagePeriodSummaryResponse:
        counts = await self.repo.get_window_counts(
            dashboard_user_id,
            start_at=start_at,
            end_at=end_at,
        )
        risk_rows = await self.repo.get_risk_distribution(
            dashboard_user_id,
            start_at=start_at,
            end_at=end_at,
            api_names=list(self.SUMMARY_RISK_API_NAMES),
        )
        risk_distribution = self._zero_risk_distribution(risk_rows)
        return UsagePeriodSummaryResponse(
            total_requests=counts["total_requests"],
            successful_requests=counts["successful_requests"],
            failed_requests=counts["failed_requests"],
            risk_category_distribution=risk_distribution,
            summary_sentence=self._build_summary_sentence(risk_distribution, period_label),
            daily_request_counts=daily_request_counts or [],
            monthly_request_counts=monthly_request_counts or [],
        )

    async def _build_time_series(
        self,
        *,
        dashboard_user_id: UUID,
        start_at: datetime,
        end_at: datetime,
        granularity: str,
        fill_start: date,
        fill_end: date,
    ) -> list[UsageRequestCountPointResponse]:
        rows = await self.repo.get_time_series_counts(
            dashboard_user_id,
            start_at=start_at,
            end_at=end_at,
            granularity=granularity,
        )
        by_period: dict[date, dict[str, int]] = {}
        for row in rows:
            period_start = self._bucket_date(row["period_start"], granularity)
            bucket = by_period.setdefault(
                period_start,
                {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                },
            )
            request_count = int(row["request_count"] or 0)
            bucket["total_requests"] += request_count
            if row["is_success"]:
                bucket["successful_requests"] += request_count
            else:
                bucket["failed_requests"] += request_count

        points: list[UsageRequestCountPointResponse] = []
        if granularity == "day":
            current = fill_start
            while current <= fill_end:
                bucket = by_period.get(
                    current,
                    {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                    },
                )
                points.append(
                    UsageRequestCountPointResponse(
                        period_start=current,
                        total_requests=bucket["total_requests"],
                        successful_requests=bucket["successful_requests"],
                        failed_requests=bucket["failed_requests"],
                    )
                )
                current += timedelta(days=1)
            return points

        current = fill_start
        while current <= fill_end:
            bucket = by_period.get(
                current,
                {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                },
            )
            points.append(
                UsageRequestCountPointResponse(
                    period_start=current,
                    total_requests=bucket["total_requests"],
                    successful_requests=bucket["successful_requests"],
                    failed_requests=bucket["failed_requests"],
                )
            )
            current = self._next_month_start(current)
        return points

    def _zero_risk_distribution(self, rows: list[dict]) -> list[UsageRiskCategoryCountResponse]:
        counts = {risk: 0 for risk in self.RISK_CATEGORY_NAMES}
        for row in rows:
            counts[str(row["risk_level"])] = int(row["request_count"] or 0)

        return [
            UsageRiskCategoryCountResponse(risk_level=risk, request_count=counts[risk])
            for risk in self.RISK_CATEGORY_NAMES
        ]

    def _build_summary_sentence(
        self,
        risk_distribution: list[UsageRiskCategoryCountResponse],
        period_label: str,
    ) -> str:
        total = sum(item.request_count for item in risk_distribution)
        if total == 0:
            return f"No dashboard lookup or score requests were recorded for {self._sample_phrase(period_label)}"

        ordered = sorted(
            (item for item in risk_distribution if item.request_count > 0),
            key=lambda item: item.request_count,
            reverse=True,
        )
        if not ordered:
            return f"No dashboard lookup or score requests were recorded for {self._sample_phrase(period_label)}"

        top = ordered[0]
        if len(ordered) > 1 and (top.request_count + ordered[1].request_count) / total >= 0.5:
            phrase = (
                f"{self._risk_sentence_label(top.risk_level)} and "
                f"{self._risk_sentence_label(ordered[1].risk_level)} vehicles continue to make up the majority "
                f"of {self._sample_phrase(period_label)}."
            )
        else:
            phrase = (
                f"{self._risk_sentence_label(top.risk_level)} vehicles continue to make up the majority "
                f"of {self._sample_phrase(period_label)}."
            )
        return phrase[:1].upper() + phrase[1:]

    def _sample_phrase(self, period_label: str) -> str:
        if period_label == "today":
            return "today's sample"
        if period_label == "month-to-date":
            return "the month-to-date sample"
        if period_label == "rolling 12-month":
            return "the rolling 12-month sample"
        return f"the {period_label} sample"

    def _risk_sentence_label(self, risk_level: str) -> str:
        labels = {
            "SEVERE": "severe-risk",
            "HIGH": "high-risk",
            "MODERATE": "moderate-risk",
            "LOW": "low",
            "EXCELLENT": "excellent-record",
            "EXEMPLARY": "clean-record",
            "UNKNOWN": "unclassified",
        }
        return labels.get(risk_level, str(risk_level).lower())

    def _success_rate_pct(self, successful_requests: int, total_requests: int) -> float:
        if total_requests <= 0:
            return 0.0
        return round((successful_requests / total_requests) * 100, 2)

    def _bucket_date(self, bucket_start: datetime, granularity: str) -> date:
        if granularity == "day":
            return bucket_start.date()
        return bucket_start.date().replace(day=1)

    def _month_start_offset(self, now: datetime, months_back: int) -> datetime:
        year = now.year
        month = now.month - months_back
        while month <= 0:
            month += 12
            year -= 1
        return datetime(year, month, 1, tzinfo=timezone.utc)

    def _next_month_start(self, value: date) -> date:
        year = value.year + (1 if value.month == 12 else 0)
        month = 1 if value.month == 12 else value.month + 1
        return date(year, month, 1)

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

    def _zero_nested_request_counts(self, ordered_keys: Sequence[str]) -> dict[str, dict[str, int]]:
        return {
            key: {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
            }
            for key in ordered_keys
        }

    def _to_api_request_count_rows(
        self,
        counts_by_api: Mapping[str, Mapping[str, int]],
    ) -> list[UsageApiRequestCountResponse]:
        return [
            UsageApiRequestCountResponse(
                api_name=api_name,
                total_requests=int(counts_by_api.get(api_name, {}).get("total_requests", 0)),
                successful_requests=int(counts_by_api.get(api_name, {}).get("successful_requests", 0)),
                failed_requests=int(counts_by_api.get(api_name, {}).get("failed_requests", 0)),
            )
            for api_name in self.API_KEY_API_NAMES
        ]
