from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, func, tuple_
from datetime import date, timedelta
import uuid
from datetime import datetime

from src.database import BaseDBRepository
from src.models import (
    ChallansFetchLog,
    Challan,
)

from src.violations.constants import SCORING_WINDOW_DAYS 


class ChallanRepository(BaseDBRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        
        
    async def get_last_fetch(self, vehicle_number: str, source_id: str) -> datetime | None:
        result = await self.db.execute(
            select(ChallansFetchLog.fetched_at)
                .where(
                    ChallansFetchLog.vehicle_number == vehicle_number,
                    ChallansFetchLog.source_id == source_id
                )
                .order_by(ChallansFetchLog.fetched_at.desc())
                .limit(1)
        )
        return result.scalar_one_or_none()
    
    
    async def get_all_active(self, vehicle_number: str):
        from_date = date.today()-timedelta(days=SCORING_WINDOW_DAYS)
        
        result = await self.db.execute(
            select(Challan)
                .where(
                    Challan.vehicle_number == vehicle_number,
                    Challan.active.is_(True),
                    Challan.challan_datetime >= from_date
                ).order_by(
                    Challan.challan_datetime.desc()
                )
        )
        return result.scalars().all()
    
    
    async def insert(self, challans: list[dict]):
        if not challans:
            return
        await self.db.execute(
            insert(Challan)
                .values(challans)
        )
        
    
    async def soft_delete(self, *, vehicle_number: str, to_delete: set[tuple[str, str]]):
        if not to_delete:
            return

        await self.db.execute(
            update(Challan)
                .where(
                    Challan.vehicle_number == vehicle_number,
                    tuple_(Challan.source_id, Challan.challan_number).in_(to_delete),
                )
                .values(
                    active=False,
                    removed_at=func.now(),
                )
        )
        
    
    async def update_fetch_log(self, vehicle_number: str, source_id: str) -> uuid.UUID | None:
        result = await self.db.execute(
            insert(ChallansFetchLog)
                .values(
                    vehicle_number=vehicle_number,
                    source_id=source_id
                ).returning(ChallansFetchLog.id)
        )
        return result.scalar_one_or_none()
