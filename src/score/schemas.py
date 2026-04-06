from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.score.types import RiskLevel


class ViolationCountsResponse(BaseModel):
    total: int
    severe: int
    moderate: int
    low: int


class DBSRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    vehicle_number: str
    score: int
    total_deductions: int
    risk_level: RiskLevel
    premium_modifier_pct: int
    violation_counts: ViolationCountsResponse
    window_start: date
    window_end: date
    last_violation_datetime: datetime | None

    
class DBSWithPremiumResponse(BaseModel):
    dbs_stats:        DBSRecordResponse
    base_premium:     int
    adjusted_premium: int