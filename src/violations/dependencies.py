from fastapi import Depends
from typing import Annotated

from src.violations.service import ChallanService
from src.violations.repository import ChallanRepository
from src.violations.ingest import ChallanIngest

from src.database import Session
from src.dependencies import GetHttpClient


async def get_challan_ingest(http_client: GetHttpClient) -> ChallanIngest:
    return ChallanIngest(client=http_client)


async def get_challan_repository(db: Session) -> ChallanRepository:
    return ChallanRepository(db)

    
async def get_challan_service(repo: Annotated[ChallanRepository, Depends(get_challan_repository)], ingest: Annotated[ChallanIngest, Depends(get_challan_ingest)]) -> ChallanService:    
    return ChallanService(repo=repo, ingest=ingest)


GetChallanService = Annotated[ChallanService, Depends(get_challan_service)]