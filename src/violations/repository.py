from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, func, tuple_, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import date, timedelta
import uuid
from datetime import datetime

from src.database import BaseDBRepository
from src.models import (
    ChallansFetchLog,
    ChallansOffenseDetail,
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


    async def get_all_for_sync(self, vehicle_number: str, source_id: str) -> list[Challan]:
        result = await self.db.execute(
            select(Challan)
                .where(
                    Challan.vehicle_number == vehicle_number,
                    Challan.source_id == source_id,
                )
        )
        return result.scalars().all()
    
    
    async def insert(self, challans: list[dict]):
        if not challans:
            return {}

        offense_name_rows: list[dict] = []
        challan_rows: list[dict] = []

        for challan in challans:
            offense_names = challan.pop("offense_names", []) or []
            challan_rows.append(challan)
            offense_name_rows.append(
                {
                    "challan_key": (challan["challan_number"], challan["source_id"]),
                    "offense_names": offense_names,
                }
            )

        result = await self.db.execute(
            pg_insert(Challan)
                .values(challan_rows)
                .on_conflict_do_update(
                    index_elements=["challan_number", "source_id"]
                    ,
                    set_={
                        "vehicle_number": pg_insert(Challan).excluded.vehicle_number,
                        "offense_details": pg_insert(Challan).excluded.offense_details,
                        "thz_category": pg_insert(Challan).excluded.thz_category,
                        "thz_description": pg_insert(Challan).excluded.thz_description,
                        "thz_deduction": pg_insert(Challan).excluded.thz_deduction,
                        "severity": pg_insert(Challan).excluded.severity,
                        "challan_place": pg_insert(Challan).excluded.challan_place,
                        "challan_datetime": pg_insert(Challan).excluded.challan_datetime,
                        "state_code": pg_insert(Challan).excluded.state_code,
                        "rto": pg_insert(Challan).excluded.rto,
                        "accused_name": pg_insert(Challan).excluded.accused_name,
                        "fine_amount": pg_insert(Challan).excluded.fine_amount,
                        "challan_status": pg_insert(Challan).excluded.challan_status,
                        "court_challan": pg_insert(Challan).excluded.court_challan,
                        "court_name": pg_insert(Challan).excluded.court_name,
                        "upstream_code": pg_insert(Challan).excluded.upstream_code,
                        "active": True,
                        "removed_at": None,
                        "updated_at": func.now(),
                    }
                )
                .returning(
                    Challan.id,
                    Challan.challan_number,
                    Challan.source_id,
                )
        )

        inserted_rows = result.mappings().all()
        challan_id_map = {
            (row["challan_number"], row["source_id"]): row["id"]
            for row in inserted_rows
        }

        challan_ids = list(challan_id_map.values())
        if challan_ids:
            await self.db.execute(
                delete(ChallansOffenseDetail)
                    .where(ChallansOffenseDetail.challan_id.in_(challan_ids))
            )

        offense_rows: list[dict] = []
        for row in offense_name_rows:
            challan_id = challan_id_map.get(row["challan_key"])
            if challan_id is None:
                continue

            for offense_name in row["offense_names"]:
                offense_rows.append(
                    {
                        "challan_id": challan_id,
                        "offense_name": offense_name,
                    }
                )

        if offense_rows:
            await self.db.execute(
                insert(ChallansOffenseDetail)
                    .values(offense_rows)
            )
        return challan_id_map
        
    
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
        
    
    async def update_fetch_log(self, vehicle_number: str, source_id: str, response_duration_ms: float) -> uuid.UUID | None:
        result = await self.db.execute(
            insert(ChallansFetchLog)
                .values(
                    vehicle_number=vehicle_number,
                    source_id=source_id,
                    response_duration_ms=response_duration_ms,
                ).returning(ChallansFetchLog.id)
        )
        return result.scalar_one_or_none()
