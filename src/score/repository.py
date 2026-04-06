from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select

from src.database import BaseDBRepository
from src.models import DBSRecord
from src.score.types import DBSStats


class ScoreRepository(BaseDBRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        
        
    async def insert(self, dbs_stats: DBSStats):
        result = await self.db.execute(
            insert(DBSRecord)
            .values(
                vehicle_number=dbs_stats.vehicle_number,
                score=dbs_stats.score,
                total_deductions=dbs_stats.total_deductions,
                risk_level=dbs_stats.risk_level.value,
                premium_modifier_pct=dbs_stats.premium_modifier_pct,
                total_violations=dbs_stats.violation_counts.total,
                severe_violations=dbs_stats.violation_counts.severe,
                moderate_violations=dbs_stats.violation_counts.moderate,
                low_violations=dbs_stats.violation_counts.low,
                window_start=dbs_stats.window_start,
                window_end=dbs_stats.window_end,
                last_violation_datetime=dbs_stats.last_violation_datetime,
            )
            .returning(DBSRecord)
        )
        return result.scalar_one()
        
    
    async def get_latest(self, vehicle_number: str):
        result = await self.db.execute(
            select(DBSRecord)
            .where(DBSRecord.vehicle_number == vehicle_number)
            .order_by(DBSRecord.computed_at.desc())
            .limit(1)
        )
        return result.scalars().first()
