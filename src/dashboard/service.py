import asyncio
from dataclasses import asdict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.dashboard.schemas import (
    BatchVehicleLookupItem,
    BatchVehicleLookupResponse,
    VehicleLookupResponse,
)
from src.dashboard.types import BatchVehicleLookupResult, VehicleLookupResult

from src.score.engine import ScoreEngine
from src.score.repository import ScoreRepository
from src.score.types import DBSStats, DBSWithPremium, RiskLevel
from src.score.service import ScoreService

from src.violations.repository import ChallanRepository
from src.violations.types import ChallanDTO
from src.violations.service import ChallanService
from src.vehicles.repository import VehicleRepository
from src.vehicles.types import VehicleDTO
from src.vehicles.service import VehicleService
from src.logging_utils import get_logger, log_event
from src.dashboard.utils import get_risk_category
from src.types import APINames, UsageStatsPerVehicle
from src.dependencies import UsageRecorder


class DashboardService:
    BATCH_LOOKUP_CONCURRENCY = 5

    def __init__(
        self,
        *,
        challan_svc: ChallanService,
        score_svc: ScoreService,
        vehicle_svc: VehicleService,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        self.challan_svc = challan_svc
        self.score_svc = score_svc
        self.vehicle_svc = vehicle_svc
        self.session_factory = session_factory
        self.logger = get_logger(__name__)
    
    
    async def vehicle_lookup(
        self,
        vehicle_number: str,
        usage: UsageRecorder,
        include_rc: bool = True,
    ) -> VehicleLookupResponse:
        log_event(self.logger, "INFO", "dashboard.lookup.start", vehicle_number=vehicle_number)
        
        try:
            lookup_result = await self._resolve_vehicle_lookup(vehicle_number, include_rc)
            log_event(
                self.logger,
                "INFO",
                "dashboard.lookup.end",
                vehicle_number=vehicle_number,
                violations=len(lookup_result.violations),
                vendor_rc_latency_ms=lookup_result.vendor_rc_latency_ms,
                vendor_challan_latency_ms=lookup_result.vendor_rc_latency_ms,
            )

            usage.store_usage([
                    UsageStatsPerVehicle(
                        api_name=APINames.DASHBOARD_SINGLE_VEHICLE_LOOKUP,
                        vehicle_number=vehicle_number,
                        risk_category=get_risk_category(lookup_result.dbs),
                        from_db_cache=lookup_result.challan_from_db_cache,
                        challan_net_changes=lookup_result.challan_net_changes,
                        vendor_challan_latency_ms=lookup_result.vendor_challan_latency_ms,
                        vendor_rc_latency_ms=lookup_result.vendor_rc_latency_ms,
                        challan_fetch_failed=lookup_result.challan_fetch_failed,
                        challan_error_info=lookup_result.challan_error_info,
                        rc_fetch_failed=lookup_result.rc_fetch_failed,
                    rc_error_info=lookup_result.rc_error_info,
                )
            ])
            
            return VehicleLookupResponse.model_validate(lookup_result)
        except Exception:
            self.logger.exception("event=dashboard.lookup.error vehicle_number=%s", vehicle_number)
            raise
        
        
    async def _resolve_vehicle_lookup(self, vehicle_number: str, include_rc: bool) -> VehicleLookupResult:
        refresh_result = await self.challan_svc.refresh_challans_if_stale(vehicle_number)
        
        if include_rc:
            vehicle = await self.vehicle_svc.get_vehicle(vehicle_number)
            vendor_rc_latency_ms = vehicle.vendor_rc_latency_ms
            rc_fetch_failed = vehicle.rc_fetch_failed
            rc_error_info = vehicle.rc_error_info
            challans = await self.challan_svc.list_active_challans(vehicle_number)
        else:
            challans = await self.challan_svc.list_active_challans(vehicle_number)
            vehicle = None
            vendor_rc_latency_ms = None
            rc_fetch_failed = False
            rc_error_info = None

        dbs = await self.score_svc.compute_dbs_by_challans_and_vehicle(
            vehicle_number=vehicle_number,
            sync_happened=refresh_result.diff,
            include_premium=include_rc,
            vehicle=vehicle,
            challans=challans,
        )

        fresh_as_of = await self.challan_svc.get_last_challan_fetch_timestamp(vehicle_number)

        return VehicleLookupResult(
            vehicle=vehicle,
            violations=challans,
            dbs=dbs,
            fresh_as_of=fresh_as_of,
            queried_at=datetime.now(),
            
            vendor_rc_latency_ms=vendor_rc_latency_ms,
            rc_fetch_failed=rc_fetch_failed,
            rc_error_info=rc_error_info,
            
            challan_fetch_failed=refresh_result.challan_fetch_failed,
            vendor_challan_latency_ms=refresh_result.vendor_latency_ms,
            challan_error_info=refresh_result.error_info,
            challan_net_changes=refresh_result.net_changes,
            challan_from_db_cache=refresh_result.from_db_cache,
        )


    def _build_lookup_service_for_session(self, session: AsyncSession) -> "DashboardService":
        challan_svc = ChallanService(
            repo=ChallanRepository(session),
            ingest=self.challan_svc.ingest,
        )
        vehicle_svc = VehicleService(
            repo=VehicleRepository(session),
            ingest=self.vehicle_svc.ingest,
        )
        score_svc = ScoreService(
            repo=ScoreRepository(session),
            engine=ScoreEngine(),
            challan_svc=challan_svc,
            vehicle_svc=vehicle_svc,
        )
        return DashboardService(
            challan_svc=challan_svc,
            score_svc=score_svc,
            vehicle_svc=vehicle_svc,
            session_factory=self.session_factory,
        )
        

    async def _batch_lookup_item(
        self,
        vehicle_number: str,
        semaphore: asyncio.Semaphore,
        include_rc: bool = True,
    ) -> BatchVehicleLookupResult | None:
        async with semaphore:
            if self.session_factory is None:
                self.logger.error("event=dashboard.lookup.batch.missing_session_factory")
                return None

            try:
                async with self.session_factory() as session:
                    lookup_service = self._build_lookup_service_for_session(session)
                    try:
                        lookup = await lookup_service._resolve_vehicle_lookup(vehicle_number, include_rc)
                    except Exception:
                        await session.rollback()
                        raise
            except Exception as e:
                logger = self.logger
                logger.exception("event=dashboard.lookup.batch.item_error vehicle_number=%s\n%s", vehicle_number, e)
                return None

        dbs_stats = lookup.dbs.dbs_stats if include_rc else lookup.dbs
        return BatchVehicleLookupResult(
            vehicle_number=vehicle_number,
            category=getattr(lookup.vehicle, "category", None),
            category_description=getattr(lookup.vehicle, "category_description", None),
            score=dbs_stats.score,
            risk_level=dbs_stats.risk_level,
            premium_modifier_pct=dbs_stats.premium_modifier_pct,
            total_violations=dbs_stats.violation_counts.total,
            vendor_rc_latency_ms=lookup.vendor_rc_latency_ms,
            vendor_latency_ms=lookup.vendor_challan_latency_ms,
            from_db_cache=lookup.challan_from_db_cache,
            rc_fetch_failed=lookup.rc_fetch_failed,
            rc_error_info=lookup.rc_error_info,
            challan_fetch_failed=lookup.challan_fetch_failed,
            challan_error_info=lookup.challan_error_info,
            challan_net_changes=lookup.challan_net_changes,
        )


    async def batch_vehicle_lookup(
        self,
        vehicle_numbers: list[str],
        usage: UsageRecorder,
        include_rc: bool = True,
    ) -> BatchVehicleLookupResponse:
        log_event(self.logger, "INFO", "dashboard.lookup.batch.start", input_count=len(vehicle_numbers))
        semaphore = asyncio.Semaphore(self.BATCH_LOOKUP_CONCURRENCY)
        results = await asyncio.gather(
            *(self._batch_lookup_item(vehicle_number, semaphore, include_rc) for vehicle_number in vehicle_numbers)
        )

        successful_results = [result for result in results if result is not None]

        usage.store_usage([
                UsageStatsPerVehicle(
                    api_name=APINames.DASHBOARD_BATCH_VEHICLE_LOOKUP,
                    vehicle_number=result.vehicle_number,
                    risk_category=result.risk_level,
                    from_db_cache=result.from_db_cache,
                    challan_net_changes=result.challan_net_changes,
                    vendor_challan_latency_ms=result.vendor_latency_ms,
                    vendor_rc_latency_ms=result.vendor_rc_latency_ms,
                    challan_fetch_failed=result.challan_fetch_failed,
                    challan_error_info=result.challan_error_info,
                rc_fetch_failed=result.rc_fetch_failed,
                rc_error_info=result.rc_error_info,
            )
            for result in successful_results
        ])

        risk_category_counts = {risk_level.value: 0 for risk_level in RiskLevel}
        for result in successful_results:
            risk_category_counts[result.risk_level] = risk_category_counts.get(result.risk_level, 0) + 1

        response = BatchVehicleLookupResponse(
            results=[
                BatchVehicleLookupItem(**asdict(result))
                for result in successful_results
            ],
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
