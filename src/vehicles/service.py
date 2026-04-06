# from sqlalchemy.ext.asyncio import AsyncSession

from src.vehicles.repository import VehicleRepository
from src.vehicles.ingest import RCIngest


class VehicleService:
    def __init__(
        self,
        *,
        repo: VehicleRepository,
        ingest: RCIngest
    ):
        self.repo = repo
        self.ingest = ingest
        
    
    async def fetch_and_store(self, vehicle_number: str):
        vehicle_rc_data = await self.ingest.fetch(vehicle_number)
        inserted_vehicle = await self.repo.insert(vehicle_rc_data)
        await self.repo.commit()
        return inserted_vehicle
        
        
    async def get_vehicle(self, vehicle_number: str):
        existing = await self.repo.get(vehicle_number)
        if not existing:
            return await self.fetch_and_store(vehicle_number)
        
        return existing