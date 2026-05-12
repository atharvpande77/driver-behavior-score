from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class UsageStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class UsageType(StrEnum):
    SINGLE = "single"
    BATCH = "batch"


@dataclass(frozen=True)
class UsageEventRequestContext:
    request_id: UUID
    dashboard_user_id: UUID
    api_key_id: UUID | None
    auth_type: str
    endpoint: str
    method: str
    usage_type: UsageType
    total_latency_ms: float
    is_success: bool
    status: UsageStatus
    error_type: str | None
    http_status_code: int
    ip_address: str | None
    user_agent: str | None
