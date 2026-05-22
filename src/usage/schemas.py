from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageRecentVehicleResponse(BaseModel):
    vehicle_number: str
    risk_category: str
    queried_at: datetime


class UsageRiskCategoryCountResponse(BaseModel):
    risk_level: str
    request_count: int


class UsageRequestCountPointResponse(BaseModel):
    period_start: date
    total_requests: int
    successful_requests: int
    failed_requests: int


class UsageApiRequestCountResponse(BaseModel):
    api_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int


class UsagePeriodSummaryResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    risk_category_distribution: list[UsageRiskCategoryCountResponse]
    summary_sentence: str
    daily_request_counts: list[UsageRequestCountPointResponse] = Field(default_factory=list)
    monthly_request_counts: list[UsageRequestCountPointResponse] = Field(default_factory=list)


class UsageSummaryResponse(BaseModel):
    request_success_rate_pct: float
    total_calls_this_month: int
    total_failed_requests_this_month: int
    last_request_at: datetime | None
    today: UsagePeriodSummaryResponse
    current_month: UsagePeriodSummaryResponse
    last_12_months: UsagePeriodSummaryResponse


class UsageApiKeyStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_by_api: list[UsageApiRequestCountResponse]


class UsageApiKeyUsageResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_by_api: list[UsageApiRequestCountResponse]
    api_keys: list[UsageApiKeyStatsResponse]
