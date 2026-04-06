from fastapi import Depends
from typing import Annotated

from src.vehicles.repository import VehicleRepository
from src.vehicles.ingest import RCIngest
from src.vehicles.service import VehicleService

from src.database import Session

    
async def get_vehicle_repository(db: Session) -> VehicleRepository:
    repo = VehicleRepository(db)
    return repo


def get_rc_ingest():
    return RCIngest()


def get_vehicle_service(
    repo: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    ingest: Annotated[RCIngest, Depends(get_rc_ingest)]
):
    return VehicleService(repo=repo, ingest=ingest)


GetVehicleService = Annotated[VehicleService, Depends(get_vehicle_service)]