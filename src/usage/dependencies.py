from typing import Annotated

from fastapi import Depends

from src.database import Session
from src.usage.repository import UsageEventRepository
from src.usage.service import UsageEventService


def get_usage_event_repository(db: Session):
    return UsageEventRepository(db)


def get_usage_event_service(
    repo: Annotated[UsageEventRepository, Depends(get_usage_event_repository)],
):
    return UsageEventService(repo=repo)


GetUsageEventService = Annotated[UsageEventService, Depends(get_usage_event_service)]
