from src.vehicles.repository import VehicleRepository
from src.vehicles.ingest import RCIngest
from src.vehicles.types import VehicleDTO
from src.vehicles.utils import mask_owner_name

from src.models import Vehicle



class VehicleService:
    def __init__(
        self,
        *,
        repo: VehicleRepository,
        ingest: RCIngest
    ):
        self.repo = repo
        self.ingest = ingest
        

    def _empty_vehicle_details(self, vehicle_number: str) -> VehicleDTO:
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
        )
        
    
    def _to_vehicle_details(self, vehicle: Vehicle) -> VehicleDTO:
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
        )


    async def _fetch_and_store(self, vehicle_number: str) -> VehicleDTO:
        vehicle_rc_data = await self.ingest.fetch(vehicle_number)
        if vehicle_rc_data is None:
            return self._empty_vehicle_details(vehicle_number)
        inserted_vehicle = await self.repo.insert(vehicle_rc_data)
        await self.repo.commit()
        return self._to_vehicle_details(inserted_vehicle)
        
        
    async def get_vehicle(self, vehicle_number: str) -> VehicleDTO:
        existing = await self.repo.get(vehicle_number)
        if not existing:
            return await self._fetch_and_store(vehicle_number)
        
        return self._to_vehicle_details(existing)