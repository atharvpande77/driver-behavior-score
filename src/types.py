from dataclasses import dataclass
from enum import StrEnum


class APINames(StrEnum):
    SCORE = "Get Vehicle Score"
    VIOLATIONS = "Get Violations"
    VEHICLES = "Get Vehicles"
    DASHBOARD_SINGLE_VEHICLE_LOOKUP = "Dashboard Single Vehicle Lookup"
    DASHBOARD_BATCH_VEHICLE_LOOKUP = "Dashboard Batch Vehicle Lookup"

# class RequestResult(StrEnum):
#     SUCCESS = "success"
#     FAILURE = "failure"


@dataclass
class UsageStatsPerVehicle:
    api_name: APINames
    vehicle_number: str
    risk_category:  str | None = None
    from_db_cache:  bool = False
    challan_net_changes: int = 0
    
    challan_fetch_failed: bool | None = None
    challan_error_info: str | None = None
    vendor_challan_latency_ms: float | None = None
    
    rc_fetch_failed: bool | None = None
    rc_error_info: str | None = None
    vendor_rc_latency_ms: float | None = None
