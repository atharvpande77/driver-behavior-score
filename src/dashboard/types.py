from dataclasses import dataclass
from datetime import datetime

from src.score.types import DBSStats, DBSWithPremium
from src.vehicles.types import VehicleDTO
from src.violations.types import ChallanDTO


@dataclass
class VehicleLookupResult:
    vehicle: VehicleDTO | None
    violations: list[ChallanDTO]
    dbs: DBSWithPremium | DBSStats
    fresh_as_of: datetime | None
    queried_at: datetime
    
    vendor_rc_latency_ms: float | None
    rc_fetch_failed: bool
    rc_error_info: str | None
    
    challan_fetch_failed: bool
    vendor_challan_latency_ms: float | None
    challan_error_info: str | None
    challan_net_changes: int
    challan_from_db_cache: bool


@dataclass
class BatchVehicleLookupResult:
    vehicle_number: str
    category: str | None
    category_description: str | None
    score: int
    risk_level: str
    premium_modifier_pct: int
    total_violations: int
    vendor_rc_latency_ms: float | None
    vendor_latency_ms: float | None
    from_db_cache: bool
    rc_fetch_failed: bool
    rc_error_info: str | None
    challan_fetch_failed: bool
    challan_error_info: str | None
    challan_net_changes: int = 0
