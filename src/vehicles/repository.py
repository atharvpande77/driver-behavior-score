from dataclasses import asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from src.vehicles.types import NormalizedRC

from src.database import BaseDBRepository
from src.models import Vehicle


class VehicleRepository(BaseDBRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        
    
    async def get(self, vehicle_number: str) -> Vehicle | None:
        vehicle = await self.db.get(Vehicle, vehicle_number)
        return vehicle
    
    
    async def insert(self, vehicle: NormalizedRC) -> Vehicle:
        payload = asdict(vehicle)
        result = await self.db.execute(
            insert(Vehicle)
                .values(**payload)
                .returning(Vehicle)
        )
        return result.scalar_one()