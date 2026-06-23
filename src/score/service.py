from datetime import date, timedelta
from src.score.repository import ScoreRepository
from src.score.engine import ScoreEngine, PremiumEngine
from src.score.types import DBSWithPremium, DBSStats, RiskLevel, ViolationCounts, DBSLookupResult

from src.violations.service import ChallanService
from src.violations.constants import SCORING_WINDOW_DAYS
from src.violations.types import ChallanDTO
from src.vehicles.service import VehicleService
from src.vehicles.types import VehicleDTO
from src.core.models import DBSRecord, Vehicle
from src.core.logging_utils import get_logger, log_event
from src.core.types import APINames, UsageStatsPerVehicle
from src.dashboard.utils import get_risk_category
from src.core.dependencies import UsageRecorder


class ScoreService:
    def __init__(
        self,
        *,
        repo: ScoreRepository,
        engine: ScoreEngine,
        challan_svc: ChallanService,
        vehicle_svc: VehicleService
    ):
        self.repo = repo
        self.engine = engine
        self.challan_svc = challan_svc
        self.vehicle_svc = vehicle_svc
        self.logger = get_logger(__name__)


    def _to_dbs_stats(self, record: DBSRecord) -> DBSStats:
        return DBSStats(
            score=record.score,
            total_deductions=record.total_deductions,
            risk_level=RiskLevel(record.risk_level),
            premium_modifier_pct=record.premium_modifier_pct,
            vehicle_number=record.vehicle_number,
            window_start=record.window_start,
            window_end=record.window_end,
            last_violation_datetime=record.last_violation_datetime,
            violation_counts=ViolationCounts(
                total=record.total_violations,
                severe=record.severe_violations,
                moderate=record.moderate_violations,
                low=record.low_violations,
            ),
        )
        
    
    async def compute_and_add_score_record(
        self,
        vehicle_number: str
    ) -> DBSRecord:
        log_event(self.logger, "INFO", "score.compute.start", vehicle_number=vehicle_number)
        active_challans = await self.challan_svc.list_active_challans(vehicle_number)
        
        window_end = date.today()
        window_start = window_end - timedelta(days=SCORING_WINDOW_DAYS)
        
        dbs_stats = self.engine.compute(
            vehicle_number,
            active_challans,
            window_start=window_start,
            window_end=window_end
        )
        
        inserted_record = await self.repo.insert(dbs_stats)
        
        await self.repo.commit()
        log_event(
            self.logger,
            "INFO",
            "score.compute.end",
            vehicle_number=vehicle_number,
            score=inserted_record.score,
            total_violations=inserted_record.total_violations,
        )
                
        return inserted_record
    
    
    async def get_dbs_record(
        self,
        vehicle_number: str,
    ) -> DBSLookupResult:
        challans_changed = await self.challan_svc.refresh_challans_if_stale(vehicle_number)
        
        if challans_changed.diff:
            log_event(self.logger, "INFO", "score.record.recompute_required", vehicle_number=vehicle_number)
            return DBSLookupResult(
                record=await self.compute_and_add_score_record(vehicle_number),
                from_db_cache=False,
                challan_net_changes=challans_changed.net_changes,
                challan_fetch_failed=challans_changed.challan_fetch_failed,
                challan_error_info=challans_changed.error_info,
                vendor_challan_latency_ms=challans_changed.vendor_latency_ms,
            )
            
        latest = await self.repo.get_latest(vehicle_number)
        
        if not latest:
            log_event(self.logger, "INFO", "score.record.cache_miss", vehicle_number=vehicle_number)
            return DBSLookupResult(
                record=await self.compute_and_add_score_record(vehicle_number),
                from_db_cache=False,
                challan_net_changes=challans_changed.net_changes,
                challan_fetch_failed=challans_changed.challan_fetch_failed,
                challan_error_info=challans_changed.error_info,
                vendor_challan_latency_ms=challans_changed.vendor_latency_ms,
            )
            
        log_event(self.logger, "INFO", "score.record.cache_hit", vehicle_number=vehicle_number)
        return DBSLookupResult(
            record=latest,
            from_db_cache=True,
            challan_net_changes=challans_changed.net_changes,
            challan_fetch_failed=challans_changed.challan_fetch_failed,
            challan_error_info=challans_changed.error_info,
            vendor_challan_latency_ms=challans_changed.vendor_latency_ms,
        )
    
    
    async def get_dbs_with_premium(
        self,
        vehicle_number: str,
        vehicle: Vehicle
    ):
        score_lookup = await self.get_dbs_record(vehicle_number)
        score_record = self._to_dbs_stats(score_lookup.record)
            
        base_premium, dbs_adjusted_premium = PremiumEngine.compute(
            score_record.premium_modifier_pct,
            vehicle.category,
            vehicle.cubic_capacity,
            vehicle.fuel_type
        )
        
        return DBSWithPremium(
            dbs_stats=score_record,
            base_premium=base_premium,
            adjusted_premium=dbs_adjusted_premium
        )
        
        
    async def get_score_response(self, vehicle_number: str, usage: UsageRecorder | None = None):
        vehicle = await self.vehicle_svc.get_vehicle(vehicle_number)
        score_lookup = await self.get_dbs_record(vehicle_number)
        score_record = self._to_dbs_stats(score_lookup.record)

        base_premium, adjusted_premium = PremiumEngine.compute(
            score_record.premium_modifier_pct,
            vehicle.category,
            vehicle.cubic_capacity,
            vehicle.fuel_type,
        )
        response = DBSWithPremium(
            dbs_stats=score_record,
            base_premium=base_premium,
            adjusted_premium=adjusted_premium
        )

        if usage is not None:
            usage.store_usage([
                UsageStatsPerVehicle(
                    api_name=APINames.SCORE,
                    vehicle_number=vehicle_number,
                    risk_category=get_risk_category(response),
                    from_db_cache=score_lookup.from_db_cache,
                    challan_net_changes=score_lookup.challan_net_changes,
                    challan_fetch_failed=score_lookup.challan_fetch_failed,
                    challan_error_info=score_lookup.challan_error_info,
                    vendor_challan_latency_ms=score_lookup.vendor_challan_latency_ms,
                    rc_fetch_failed=vehicle.rc_fetch_failed,
                    rc_error_info=vehicle.rc_error_info,
                    vendor_rc_latency_ms=vehicle.vendor_rc_latency_ms,
                )
            ])

        return response
        
        
    async def _compute_and_store(
        self,
        vehicle_number: str,
        challans: list[ChallanDTO],
    ):
        window_end = date.today()
        window_start = window_end - timedelta(days=SCORING_WINDOW_DAYS)
        
        dbs_stats = self.engine.compute(
            vehicle_number,
            challans,
            window_start=window_start,
            window_end=window_end
        )
        
        inserted_record = await self.repo.insert(dbs_stats)
        await self.repo.commit()
        return inserted_record
        
        
    async def _get_or_compute(
        self,
        sync_happened: bool,
        vehicle_number: str,
        challans: list[ChallanDTO]
    ):
        if sync_happened:
            return await self._compute_and_store(vehicle_number, challans)
        
        latest = await self.repo.get_latest(vehicle_number)
        if not latest:
            return await self._compute_and_store(vehicle_number, challans)
        return latest
        

    # Use this
    async def compute_dbs_by_challans_and_vehicle(
        self,
        vehicle_number: str,
        *,
        sync_happened: bool,
        challans: list[ChallanDTO],
        include_premium: bool = False,
        vehicle: VehicleDTO | None = None,
    ):
        record = self._to_dbs_stats(
            await self._get_or_compute(sync_happened, vehicle_number, challans)
        )
        
        if not include_premium or not vehicle:
            return record

        
        base_premium, adjusted_premium = PremiumEngine.compute(
            record.premium_modifier_pct,
            vehicle.category,
            vehicle.cubic_capacity,
            vehicle.fuel_type,
        )

        return DBSWithPremium(
            dbs_stats=record,
            base_premium=base_premium,
            adjusted_premium=adjusted_premium
        )
