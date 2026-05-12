from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageRecentVehicleResponse(BaseModel):
    vehicle_number: str
    risk_category: str
    queried_at: datetime


class UsageWindowSummaryResponse(BaseModel):
    total_requests: int
    total_unique_vehicles: int
    requests_by_api: dict[str, int]
    risk_category_counts: dict[str, int]


class UsageSummaryResponse(BaseModel):
    today: UsageWindowSummaryResponse
    last_seven_days: UsageWindowSummaryResponse
    current_month: UsageWindowSummaryResponse


class UsageApiKeyStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    total_requests: int
    requests_by_api: dict[str, int]
