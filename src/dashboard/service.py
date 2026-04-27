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
    
    
    async def vehicle_lookup(self, vehicle_number: str, include_rc: bool = True):
        log_event(self.logger, "INFO", "dashboard.lookup.start", vehicle_number=vehicle_number)
        
        try:
            response = await self._resolve_vehicle_lookup(vehicle_number, include_rc)
            log_event(
                self.logger,
                "INFO",
                "dashboard.lookup.end",
                vehicle_number=vehicle_number,
                violations=len(response.violations),
            )
            return response
        except Exception:
            self.logger.exception("event=dashboard.lookup.error vehicle_number=%s", vehicle_number)
            raise


    async def _resolve_vehicle_lookup(self, vehicle_number: str, include_rc: bool) -> VehicleLookupResponse:
        sync_happened: bool = await self.challan_svc.refresh_challans_if_stale(vehicle_number)
        
        if include_rc:
            # vehicle, challans = await asyncio.gather(
            #     self.vehicle_svc.get_vehicle(vehicle_number),
            #     self.challan_svc.list_active_challans(vehicle_number),
            # )
            vehicle = await self.vehicle_svc.get_vehicle(vehicle_number)
            challans = await self.challan_svc.list_active_challans(vehicle_number)
        else:
            challans = await self.challan_svc.list_active_challans(vehicle_number)
            vehicle = None

        dbs = await self.score_svc.compute_dbs_by_challans_and_vehicle(
            vehicle_number=vehicle_number,
            sync_happened=sync_happened,
            include_premium=include_rc,
            vehicle=vehicle,
            challans=challans,
        )

        fresh_as_of = await self.challan_svc.get_last_challan_fetch_timestamp(vehicle_number)

        return VehicleLookupResponse(
            vehicle=vehicle,
            violations=challans,
            dbs=dbs,
            fresh_as_of=fresh_as_of,
            queried_at=datetime.now(),
        )
        


    async def _batch_lookup_item(
        self,
        vehicle_number: str,
        semaphore: asyncio.Semaphore,
        include_rc: bool = True,
    ) -> BatchVehicleLookupItem | None:
        async with semaphore:
            try:
                lookup = await self._resolve_vehicle_lookup(vehicle_number, include_rc)
            except Exception as e:
                logger = self.logger
                logger.exception("event=dashboard.lookup.batch.item_error vehicle_number=%s\n%s", vehicle_number, e)
                return None

        dbs_stats = lookup.dbs.dbs_stats if include_rc else lookup.dbs
        return BatchVehicleLookupItem(
            vehicle_number=vehicle_number,
            category=getattr(lookup.vehicle, "category", None),
            category_description=getattr(lookup.vehicle, "category_description", None),
            score=dbs_stats.score,
            risk_level=dbs_stats.risk_level,
            premium_modifier_pct=dbs_stats.premium_modifier_pct,
            total_violations=dbs_stats.violation_counts.total,
        )


    async def batch_vehicle_lookup(
        self,
        vehicle_numbers: list[str],
        include_rc: bool = True,
    ) -> BatchVehicleLookupResponse:
        log_event(self.logger, "INFO", "dashboard.lookup.batch.start", input_count=len(vehicle_numbers))
        semaphore = asyncio.Semaphore(self.BATCH_LOOKUP_CONCURRENCY)
        results = await asyncio.gather(
            *(self._batch_lookup_item(vehicle_number, semaphore, include_rc) for vehicle_number in vehicle_numbers)
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
