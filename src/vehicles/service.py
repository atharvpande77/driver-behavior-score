from src.vehicles.repository import VehicleRepository
from src.vehicles.ingest import RCIngest
from src.vehicles.types import VehicleDTO, NormalizedRCFetchResult
from src.vehicles.utils import mask_owner_name

from src.core.models import Vehicle
from src.core.types import APINames, UsageStatsPerVehicle
from src.core.dependencies import UsageRecorder



class VehicleService:
    def __init__(
        self,
        *,
        repo: VehicleRepository,
        ingest: RCIngest
    ):
        self.repo = repo
        self.ingest = ingest


    def _empty_vehicle_details(
        self,
        vehicle_number: str,
        *,
        vendor_rc_latency_ms: float | None = None,
        rc_fetch_failed: bool = False,
        rc_error_info: str | None = None,
    ) -> VehicleDTO:
        state_code = vehicle_number[:2].upper() if len(vehicle_number) >= 2 else None
        return VehicleDTO(
            vehicle_number=vehicle_number,
            state_code=state_code,
            category=None,
            category_description=None,
            maker_description=None,
            maker_model=None,
            body_type=None,
            fuel_type=None,
            color=None,
            manufacturing_date=None,
            cubic_capacity=None,
            owner_name=None,
            rto_code=None,
            vendor_latency_ms=vendor_rc_latency_ms,
            vendor_rc_latency_ms=vendor_rc_latency_ms,
            rc_fetch_failed=rc_fetch_failed,
            rc_error_info=rc_error_info,
        )
        
    
    def _to_vehicle_details(self, vehicle: Vehicle, vendor_rc_latency_ms: float | None) -> VehicleDTO:
        return VehicleDTO(
            vehicle_number=vehicle.vehicle_number,
            state_code=vehicle.state_code,
            category=vehicle.category,
            category_description=vehicle.category_description,
            maker_description=vehicle.maker_description,
            maker_model=vehicle.maker_model,
            body_type=vehicle.body_type,
            fuel_type=vehicle.fuel_type,
            color=vehicle.color,
            manufacturing_date=vehicle.manufacturing_date,
            cubic_capacity=float(vehicle.cubic_capacity) if vehicle.cubic_capacity is not None else None,
            owner_name=mask_owner_name(vehicle.owner_name),
            rto_code=vehicle.rto_code,
            vendor_latency_ms=vendor_rc_latency_ms,
            vendor_rc_latency_ms=vendor_rc_latency_ms,
            rc_fetch_failed=False,
            rc_error_info=None,
        )


    async def _fetch_and_store(self, vehicle_number: str) -> VehicleDTO:
        fetch_result: NormalizedRCFetchResult = await self.ingest.fetch(vehicle_number)
        if fetch_result.rc_fetch_failed or fetch_result.vehicle is None:
            return self._empty_vehicle_details(
                vehicle_number,
                vendor_rc_latency_ms=fetch_result.vendor_rc_latency_ms,
                rc_fetch_failed=True,
                rc_error_info=fetch_result.rc_error_info,
            )

        inserted_vehicle = await self.repo.insert(fetch_result.vehicle)
        await self.repo.commit()
        return self._to_vehicle_details(
            inserted_vehicle,
            fetch_result.vendor_rc_latency_ms,
        )
        
        
    async def get_vehicle(
        self,
        vehicle_number: str,
        usage: UsageRecorder | None = None,
    ) -> VehicleDTO:
        existing = await self.repo.get(vehicle_number)
        if not existing:
            vehicle = await self._fetch_and_store(vehicle_number)
        else:
            vehicle = self._to_vehicle_details(existing, None)

        if usage is not None:
            usage.store_usage([
                UsageStatsPerVehicle(
                    api_name=APINames.VEHICLES,
                    vehicle_number=vehicle_number,
                    risk_category=None,
                    from_db_cache=existing is not None,
                    rc_fetch_failed=vehicle.rc_fetch_failed,
                    rc_error_info=vehicle.rc_error_info,
                    vendor_rc_latency_ms=vehicle.vendor_rc_latency_ms,
                )
            ])

        return vehicle
