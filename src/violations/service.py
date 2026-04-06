import asyncio

from src.violations.repository import ChallanRepository
from src.violations.ingest import ChallanIngest
from src.violations.constants import (
    TTL_HOURS,
    CLASSIFICATION_CONCURRENCY_LIMIT,
    THZ_CATEGORY_PRIORITY,
    THZ_CATEGORY_META,
    THZ_KEYWORD_RULES,
)
from src.violations.types import NormalizedChallan, THZCategory, THZCategoryMatch
from src.violations.utils import get_severity_from_thz_category, none_if_blank, build_classification_corpus, normalize_offense_text, needs_fetch

from src.models import Challan
from src.logging_utils import get_logger, log_event


class ChallanService:
    def __init__(
        self,
        *,
        repo: ChallanRepository,
        ingest: ChallanIngest
    ):
        self.repo = repo
        self.ingest = ingest
        self.logger = get_logger(__name__)
        
        
    async def _get_last_challan_fetch_timestamp(self, vehicle_number: str):
        source_id = self.ingest.source_id
        return await self.repo.get_last_fetch(vehicle_number, source_id)
        
        
    async def refresh_challans_if_stale(self, vehicle_number: str) -> bool:
        """Refresh challans for the given vehicle number if the source data is stale. Returns True if anything changed."""
        
        last_fetch_timestamp = await self._get_last_challan_fetch_timestamp(vehicle_number)
        
        if last_fetch_timestamp and not needs_fetch(last_fetch_timestamp, TTL_HOURS):
            log_event(self.logger, "INFO", "challan.refresh.skip_fresh_cache", vehicle_number=vehicle_number)
            return False
        
        diff = await self._refresh_challans_from_source(vehicle_number)
        log_event(self.logger, "INFO", "challan.refresh.completed", vehicle_number=vehicle_number, changed=diff)
        return diff
        
        
    async def list_active_challans(self, vehicle_number: str) -> list[Challan]:
        """Return all active challans for the given vehicle number without triggering a fetch."""
        
        challans = await self.repo.get_all_active(vehicle_number)
        return challans
    
    
    async def get_active_challans(self, vehicle_number: str):
        """Refresh challans if stale, then return the active challans for the vehicle."""
        
        await self.refresh_challans_if_stale(vehicle_number)
        return await self.repo.get_all_active(vehicle_number)
        
    
    async def _refresh_challans_from_source(self, vehicle_number: str) -> bool:
        diff: bool = False
        
        try:
            source_id, fresh_challans = await self.ingest.fetch(vehicle_number)
        except Exception as e:
            self.logger.exception(
                "event=challan.refresh.fetch_failed vehicle_number=%s source_id=%s error=%s",
                vehicle_number,
                self.ingest.source_id,
                str(e),
            )
            return diff
        
        fresh_challans_map: dict[tuple[str, str], NormalizedChallan] = {
            (c.source_id, c.challan_number): c for c in fresh_challans
        }
        
        existing = await self.repo.get_all_active(vehicle_number)
        
        existing_map: dict[tuple[str, str], Challan] = {
            (c.source_id, c.challan_number): c for c in existing
        }
        
        fresh_challans_keys = set(fresh_challans_map.keys())
        existing_keys = set(existing_map.keys())
        
        to_insert = fresh_challans_keys - existing_keys
        to_delete = existing_keys - fresh_challans_keys
        
        classification_semaphore = asyncio.Semaphore(CLASSIFICATION_CONCURRENCY_LIMIT)
        challans_to_insert = await asyncio.gather(
            *(self._build_challan_to_insert(
                vehicle_number=vehicle_number,
                challan=fresh_challans_map[(sid, cn)],
                classification_semaphore=classification_semaphore,
            ) for sid, cn in to_insert)
        )
        
        await self.repo.insert(challans_to_insert)
        
        await self.repo.soft_delete(vehicle_number=vehicle_number, to_delete=to_delete)
        
        await self.repo.update_fetch_log(
            vehicle_number=vehicle_number,
            source_id=source_id
        )
        
        await self.repo.commit()
        
        diff = bool(to_insert or to_delete)
        log_event(
            self.logger,
            "INFO",
            "challan.refresh.diff_applied",
            vehicle_number=vehicle_number,
            source_id=source_id,
            inserts=len(to_insert),
            deletes=len(to_delete),
            changed=diff,
        )
        return diff
    
    
    # Currently sync, so semaphore is useless, but keeping the logic here for when we parallelize classification in the future
    
    async def _classify(self, offense_details: str, offenses: list[str]) -> THZCategoryMatch:
        corpus = build_classification_corpus(offense_details, offenses)
        if not corpus:
            return self._thz_from_code(THZCategory.THZ_12)

        tokens = set(corpus.split())
        scores: dict[THZCategory, int] = {code: 0 for code in THZ_CATEGORY_PRIORITY}

        for code, keywords in THZ_KEYWORD_RULES.items():
            for raw_keyword in keywords:
                keyword = normalize_offense_text(raw_keyword)
                if not keyword:
                    continue
                if " " in keyword:
                    if keyword in corpus:
                        scores[code] += 2
                elif keyword in tokens or keyword in corpus:
                    scores[code] += 1

        best_code = THZCategory.THZ_12
        best_score = 0
        for code in THZ_CATEGORY_PRIORITY:
            score = scores.get(code, 0)
            if score > best_score:
                best_code = code
                best_score = score

        if best_score == 0:
            return self._thz_from_code(THZCategory.THZ_12)
        return self._thz_from_code(best_code)


    def _thz_from_code(self, code: THZCategory) -> THZCategoryMatch:
        return THZ_CATEGORY_META[code]
    

    async def _build_challan_to_insert(
        self,
        *,
        vehicle_number: str,
        challan: NormalizedChallan,
        classification_semaphore: asyncio.Semaphore,
    ) -> dict:
        offenses = [o.offense_name for o in challan.offenses]
        async with classification_semaphore:
            thz_category = await self._classify(challan.offense_details, offenses)

        return {
            "vehicle_number": vehicle_number,
            "challan_number": challan.challan_number,
            "source_id": challan.source_id,
            "offense_details": none_if_blank(challan.offense_details),
            "thz_category": none_if_blank(thz_category.category),
            "thz_description": none_if_blank(thz_category.description),
            "thz_deduction": thz_category.deduction,
            "severity": get_severity_from_thz_category(THZCategory(thz_category.category)),
            "challan_place": none_if_blank(challan.challan_place),
            "challan_datetime": challan.challan_datetime,
            "state_code": none_if_blank(challan.state_code),
            "rto": none_if_blank(challan.rto),
            "accused_name": none_if_blank(challan.accused_name),
            "fine_amount": challan.fine_amount,
            "challan_status": none_if_blank(challan.challan_status),
            "court_challan": challan.court_challan,
            "court_name": none_if_blank(challan.court_name),
            "upstream_code": none_if_blank(challan.upstream_code),
            "active": True,
        }
