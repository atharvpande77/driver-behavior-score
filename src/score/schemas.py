from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.score.types import RiskLevel


class ChallanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    challan_number: str
    challan_datetime: datetime
    fine_amount: int | None
    severity: str
    challan_place: str | None
    offense_details: str | None
    thz_category_name: str | None
    thz_category_description: str | None
    thz_category_deduction: int | None
    thz_deduction: int
    challan_status: str | None


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
    violations:       list[ChallanResponse]