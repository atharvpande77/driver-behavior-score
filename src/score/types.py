from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

from src.core.models import DBSRecord

class RiskLevel(str, Enum):
    SEVERE = "SEVERE"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    EXCELLENT = "EXCELLENT"
    EXEMPLARY = "EXEMPLARY"


@dataclass
class ViolationCounts:
    total: int = 0
    severe: int = 0
    moderate: int = 0
    low: int = 0


@dataclass
class DBSStats:
    score: int
    total_deductions: int
    risk_level: RiskLevel
    premium_modifier_pct: int
    vehicle_number: str
    window_start: date
    window_end: date
    last_violation_datetime: datetime | None = None
    violation_counts: ViolationCounts = field(default_factory=ViolationCounts)
    
    
@dataclass
class DBSWithPremium:
    dbs_stats:        DBSStats
    base_premium:     int | None
    adjusted_premium: int | None


@dataclass
class DBSLookupResult:
    record: DBSRecord
    from_db_cache: bool
    challan_net_changes: int = 0
    challan_fetch_failed: bool = False
    challan_error_info: str | None = None
    vendor_challan_latency_ms: float | None = None
