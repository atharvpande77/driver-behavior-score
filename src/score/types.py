from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

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
