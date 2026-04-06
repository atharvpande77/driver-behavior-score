import asyncio
from datetime import datetime

from src.dashboard.schemas import (
    BatchVehicleLookupItem,
    BatchVehicleLookupResponse,
    VehicleLookupResponse,
)

from src.score.types import RiskLevel
from src.score.service import ScoreService
from src.violations.service import ChallanService
from src.vehicles.service import VehicleService
from src.logging_utils import get_logger, log_event


class DashboardService:
    BATCH_LOOKUP_CONCURRENCY = 10

    def __init__(
        self,
        *,
        challan_svc: ChallanService,
        score_svc: ScoreService,
        vehicle_svc: VehicleService
    ):
        self.challan_svc = challan_svc
        self.score_svc = score_svc
        self.vehicle_svc = vehicle_svc
        self.logger = get_logger(__name__)
    
    
    async def vehicle_lookup(self, vehicle_number: str):
        log_event(self.logger, "INFO", "dashboard.lookup.start", vehicle_number=vehicle_number)
        
        try:
            vehicle, challans = await asyncio.gather(
                self.vehicle_svc.get_vehicle(vehicle_number),
                self.challan_svc.get_active_challans(vehicle_number),
            )
            
            dbs = await self.score_svc.get_dbs_with_premium(vehicle_number, vehicle)
            
            fresh_as_of = await self.challan_svc._get_last_challan_fetch_timestamp(vehicle_number)
            
            queried_at = datetime.now()
            
            response = VehicleLookupResponse(
                vehicle=vehicle,
                violations=challans,
                dbs=dbs,
                fresh_as_of=fresh_as_of,
                queried_at=queried_at,
            )
            log_event(
                self.logger,
                "INFO",
                "dashboard.lookup.end",
                vehicle_number=vehicle_number,
                violations=len(challans),
            )
            return response
        except Exception:
            self.logger.exception("event=dashboard.lookup.error vehicle_number=%s", vehicle_number)
            raise
        


    async def _batch_lookup_item(
        self,
        vehicle_number: str,
        semaphore: asyncio.Semaphore,
    ) -> BatchVehicleLookupItem | None:
        async with semaphore:
            try:
                vehicle = await self.vehicle_svc.get_vehicle(vehicle_number)
                dbs = await self.score_svc.get_dbs_with_premium(vehicle_number, vehicle)
            except Exception:
                logger = self.logger
                logger.exception("event=dashboard.lookup.batch.item_error vehicle_number=%s", vehicle_number)
                return None

        dbs_stats = dbs.dbs_stats
        return BatchVehicleLookupItem(
            vehicle_number=vehicle_number,
            category=vehicle.category,
            category_description=vehicle.category_description,
            score=dbs_stats.score,
            risk_level=dbs_stats.risk_level,
            premium_modifier_pct=dbs_stats.premium_modifier_pct,
            total_violations=dbs_stats.total_violations,
        )


    async def batch_vehicle_lookup(self, vehicle_numbers: list[str]) -> BatchVehicleLookupResponse:
        log_event(self.logger, "INFO", "dashboard.lookup.batch.start", input_count=len(vehicle_numbers))
        semaphore = asyncio.Semaphore(self.BATCH_LOOKUP_CONCURRENCY)
        results = await asyncio.gather(
            *(self._batch_lookup_item(vehicle_number, semaphore) for vehicle_number in vehicle_numbers)
        )

        successful_results = [result for result in results if result is not None]

        risk_category_counts = {risk_level.value: 0 for risk_level in RiskLevel}
        for result in successful_results:
            risk_category_counts[result.risk_level] = risk_category_counts.get(result.risk_level, 0) + 1

        response = BatchVehicleLookupResponse(
            results=successful_results,
            total_results=len(successful_results),
            risk_category_counts=risk_category_counts,
        )
        log_event(
            self.logger,
            "INFO",
            "dashboard.lookup.batch.end",
            input_count=len(vehicle_numbers),
            success_count=len(successful_results),
        )
        return response
