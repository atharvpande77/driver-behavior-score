from fastapi import Depends
from typing import Annotated

from src.violations.service import ChallanService
from src.violations.repository import ChallanRepository
from src.violations.ingest import ChallanIngest

from src.database import Session
    
async def get_challan_service(db: Session) -> ChallanService:
    repo = ChallanRepository(db)
    ingest = ChallanIngest()
    
    return ChallanService(repo=repo, ingest=ingest)

GetChallanService = Annotated[ChallanService, Depends(get_challan_service)]