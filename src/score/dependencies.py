from typing import Annotated
from fastapi import Depends

from src.score.repository import ScoreRepository
from src.score.engine import ScoreEngine
from src.score.service import ScoreService

from src.violations.dependencies import get_challan_service
from src.violations.service import ChallanService
from src.core.database import Session


def get_score_repository(db: Session):
    return ScoreRepository(db)

def get_score_engine():
    return ScoreEngine()

def get_score_service(
    repo: Annotated[ScoreRepository, Depends(get_score_repository)],
    engine: Annotated[ScoreEngine, Depends(get_score_engine)],
    challan_svc: Annotated[ChallanService, Depends(get_challan_service)],
):
    return ScoreService(
        repo=repo,
        engine=engine,
        challan_svc=challan_svc,
    )


GetScoreService = Annotated[ScoreService, Depends(get_score_service)]