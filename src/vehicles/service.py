from src.models import Vehicle
from src.vehicles.repository import VehicleRepository
from src.vehicles.ingest import RCIngest
from src.vehicles.types import VehicleDTO


class VehicleService:
    def __init__(
        self,
        *,
        repo: VehicleRepository,
        ingest: RCIngest
    ):
        self.repo = repo
        self.ingest = ingest
        
    
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
            owner_name=vehicle.owner_name,
            rto_code=vehicle.rto_code,
        )


    async def _fetch_and_store(self, vehicle_number: str) -> VehicleDTO:
        vehicle_rc_data = await self.ingest.fetch(vehicle_number)
        inserted_vehicle = await self.repo.insert(vehicle_rc_data)
        await self.repo.commit()
        return self._to_vehicle_details(inserted_vehicle)
        
        
    async def get_vehicle(self, vehicle_number: str) -> VehicleDTO:
        existing = await self.repo.get(vehicle_number)
        if not existing:
            return await self._fetch_and_store(vehicle_number)
        
        return self._to_vehicle_details(existing)
