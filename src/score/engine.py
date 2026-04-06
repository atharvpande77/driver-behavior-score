from datetime import date

from src.score.types import DBSStats, ViolationCounts, RiskLevel

from src.models import Challan
from src.violations.types import ChallanSeverity


class ScoreEngine:
    _RISK_BANDS: dict[range, tuple[RiskLevel, int]] = {
        range(285, 301): (RiskLevel.EXEMPLARY, -20),
        range(270, 285): (RiskLevel.EXCELLENT, -10),
        range(240, 270): (RiskLevel.LOW, 25),
        range(210, 240): (RiskLevel.MODERATE, 50),
        range(180, 210): (RiskLevel.HIGH, 75),
        range(150, 180): (RiskLevel.HIGH, 100),
        range(120, 150): (RiskLevel.SEVERE, 125),
        range(90, 120): (RiskLevel.SEVERE, 150),
        range(60, 90): (RiskLevel.SEVERE, 175),
        range(0, 60): (RiskLevel.SEVERE, 200),
    }
    
    
    @staticmethod
    def compute(
        vehicle_number: str,
        challans: list[Challan],
        *,
        window_start: date,
        window_end: date
    ):
        MAX_SCORE = 300
        MIN_SCORE = 0
        
        deductions = sum(getattr(challan, "thz_deduction", 0) for challan in challans)
        
        score = max(MIN_SCORE, MAX_SCORE - deductions)
        
        total_violations = len(challans)
        
        severity_counts = tuple(
            sum(getattr(challan, "severity", None) == sev for challan in challans)
            for sev in (
                ChallanSeverity.SEVERE,
                ChallanSeverity.MODERATE,
                ChallanSeverity.LOW,
            )
        )
        severe_count, moderate_count, low_count = severity_counts
        
        last_violation_datetime = max(
            (getattr(challan, "challan_datetime", None) for challan in challans),
            default=None,
        )

        risk_level, premium_modifier_pct = ScoreEngine._get_risk_level(score)
        
        return DBSStats(
            vehicle_number=vehicle_number,
            score=score,
            total_deductions=deductions,
            risk_level=risk_level,
            premium_modifier_pct=premium_modifier_pct,
            last_violation_datetime=last_violation_datetime,
            window_start=window_start,
            window_end=window_end,
            violation_counts=ViolationCounts(
                total=total_violations,
                severe=severe_count,
                moderate=moderate_count,
                low=low_count,
            ),
        )
        

    def _get_risk_level(score: int) -> tuple[RiskLevel, int]:
        bounded_score = max(0, min(score, 300))
        for score_range, outcome in ScoreEngine._RISK_BANDS.items():
            if bounded_score in score_range:
                return outcome
        return RiskLevel.SEVERE, 200
    
    
class PremiumEngine:
    def _compute_base_premium(vehicle_category: str, cubic_capacity: float, fuel_type: str) -> int | None:
        """
        Returns base annual premium based on cc-based categories only.

        Supported:
        - LMV (private cars)
        - LPV (car taxis, <=6 passengers)
        - 2WN (two wheelers)

        Returns None for:
        - ELECTRIC vehicles
        - Non-cc-based categories (HPV, HGV, etc.)
        """

        # 1. Ignore EVs
        if fuel_type.upper() == "ELECTRIC":
            return None

        vehicle_category = vehicle_category.upper()

        # PRIVATE CARS (LMV)
        if vehicle_category == "LMV":
            if cubic_capacity <= 1000:
                return 2094
            elif cubic_capacity <= 1500:
                return 3416
            else:
                return 7897

        # CAR TAXI (LPV <= 6 passengers)
        elif vehicle_category == "LPV":
            if cubic_capacity <= 1000:
                return 6040
            elif cubic_capacity <= 1500:
                return 7940
            else:
                return 10523

        # TWO WHEELERS (2WN)
        elif vehicle_category == "2WN":
            if cubic_capacity <= 75:
                return 538
            elif cubic_capacity <= 150:
                return 714
            elif cubic_capacity <= 350:
                return 1366
            else:
                return 2804

        # EVERYTHING ELSE
        return None
    
    
    @staticmethod
    def compute(
        premium_modifier_pct: int,
        vehicle_category: str,
        cubic_capacity: float,
        fuel_type: str
    ) -> tuple[int | None, int | None]:
        base_premium = PremiumEngine._compute_base_premium(vehicle_category, cubic_capacity, fuel_type)
        if base_premium is None:
            return None, None
        
        dbs_adjustment = base_premium * (premium_modifier_pct / 100)
        dbs_adjusted_premium = int(round(base_premium + dbs_adjustment))
        return base_premium, dbs_adjusted_premium
