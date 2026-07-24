from typing import Annotated
from fastapi import Depends

from src.core.database import Session
from src.telematics.repository import TelematicsRepository
from src.telematics.service import TelematicsService


def get_telematics_repository(db: Session) -> TelematicsRepository:
    return TelematicsRepository(db)


def get_telematics_service(
    repo: Annotated[TelematicsRepository, Depends(get_telematics_repository)],
) -> TelematicsService:
    return TelematicsService(repo=repo)


GetTelematicsService = Annotated[TelematicsService, Depends(get_telematics_service)]
