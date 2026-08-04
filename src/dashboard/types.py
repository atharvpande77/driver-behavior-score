from dataclasses import dataclass
from datetime import datetime

from src.score.types import DBSStats
from src.violations.types import ChallanDTO


@dataclass
class VehicleLookupResult:
    vehicle_number: str | None
    violations: list[ChallanDTO]
    dbs: DBSStats
    fresh_as_of: datetime | None
    queried_at: datetime

    challan_fetch_failed: bool
    vendor_challan_latency_ms: float | None
    challan_error_info: str | None
    challan_net_changes: int
    challan_from_db_cache: bool


@dataclass
class BatchVehicleLookupResult:
    vehicle_number: str
    score: int
    risk_level: str
    premium_modifier_pct: int
    total_violations: int
    vendor_latency_ms: float | None
    from_db_cache: bool
    challan_fetch_failed: bool
    challan_error_info: str | None
    challan_net_changes: int = 0
