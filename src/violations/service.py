import asyncio

from openai import AsyncOpenAI

from src.config import app_settings
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
from src.violations.types import ChallanDTO
from src.models import Challan
from src.logging_utils import get_logger, log_event


class ChallanService:
    OPENAI_CLASSIFICATION_MODEL = "gpt-5.4-nano-2026-03-17"

    def __init__(
        self,
        *,
        repo: ChallanRepository,
        ingest: ChallanIngest
    ):
        self.repo = repo
        self.ingest = ingest
        self.logger = get_logger(__name__)
        self.openai_client = AsyncOpenAI(api_key=app_settings.OPENAI_API_KEY)
        
        
    async def get_last_challan_fetch_timestamp(self, vehicle_number: str):
        source_id = self.ingest.source_id
        return await self.repo.get_last_fetch(vehicle_number, source_id)
        
        
    async def refresh_challans_if_stale(self, vehicle_number: str) -> bool:
        """Refresh challans for the given vehicle number if the source data is stale. Returns True if anything changed."""
        
        last_fetch_timestamp = await self.get_last_challan_fetch_timestamp(vehicle_number)
        
        if last_fetch_timestamp and not needs_fetch(last_fetch_timestamp, TTL_HOURS):
            log_event(self.logger, "INFO", "challan.refresh.skip_fresh_cache", vehicle_number=vehicle_number)
            return False
        
        diff = await self._refresh_challans_from_source(vehicle_number)
        log_event(self.logger, "INFO", "challan.refresh.completed", vehicle_number=vehicle_number, changed=diff)
        return diff
        
        
    def _to_challan_dto(self, challan) -> ChallanDTO:
        return ChallanDTO(
            challan_number=challan.challan_number,
            challan_datetime=challan.challan_datetime,
            fine_amount=challan.fine_amount,
            severity=challan.severity,
            challan_place=challan.challan_place,
            offense_details=challan.offense_details,
            thz_category_name=challan.thz_category,
            thz_category_description=challan.thz_description,
            thz_category_deduction=challan.thz_deduction,
            thz_deduction=challan.thz_deduction,
            challan_status=challan.challan_status,
        )


    async def list_active_challans(self, vehicle_number: str) -> list[ChallanDTO]:
        """Return all active challans for the given vehicle number without triggering a fetch."""
        
        challans = await self.repo.get_all_active(vehicle_number)
        if not challans:
            return []
        return [self._to_challan_dto(challan) for challan in challans]
    
    
    async def get_active_challans(self, vehicle_number: str) -> list[ChallanDTO]:
        """Refresh challans if stale, then return the active challans for the vehicle."""
        
        await self.refresh_challans_if_stale(vehicle_number)
        challans = await self.repo.get_all_active(vehicle_number)
        if not challans:
            return []
        return [self._to_challan_dto(challan) for challan in challans]
        
    
    async def _refresh_challans_from_source(self, vehicle_number: str) -> bool:
        diff: bool = False
        
        try:
            source_id, fresh_challans, response_duration_ms = await self.ingest.fetch(vehicle_number)
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
        
        existing = await self.repo.get_all_for_sync(vehicle_number, source_id)
        
        existing_map: dict[tuple[str, str], Challan] = {
            (c.source_id, c.challan_number): c for c in existing
        }
        
        fresh_challans_keys = set(fresh_challans_map.keys())
        existing_keys = set(existing_map.keys())
        
        to_delete = existing_keys - fresh_challans_keys
        
        classification_semaphore = asyncio.Semaphore(CLASSIFICATION_CONCURRENCY_LIMIT)
        challan_payloads = await asyncio.gather(
            *(self._build_challan_to_insert(
                vehicle_number=vehicle_number,
                challan=challan,
                classification_semaphore=classification_semaphore,
            ) for challan in fresh_challans)
        )

        await self.repo.insert(challan_payloads)
        
        await self.repo.soft_delete(vehicle_number=vehicle_number, to_delete=to_delete)
        
        await self.repo.update_fetch_log(
            vehicle_number=vehicle_number,
            source_id=source_id,
            response_duration_ms=response_duration_ms,
        )
        
        await self.repo.commit()
        
        diff = bool(to_delete)
        if not diff:
            for payload in challan_payloads:
                key = (payload["source_id"], payload["challan_number"])
                current = existing_map.get(key)
                if current is None or self._challan_payload_changed(current, payload):
                    diff = True
                    break
        log_event(
            self.logger,
            "INFO",
            "challan.refresh.diff_applied",
            vehicle_number=vehicle_number,
            source_id=source_id,
            upserts=len(challan_payloads),
            deletes=len(to_delete),
            changed=diff,
        )
        return diff


    def _challan_payload_changed(self, current: Challan, payload: dict) -> bool:
        return any(
            (
                current.vehicle_number != payload["vehicle_number"],
                current.offense_details != payload["offense_details"],
                current.thz_category != payload["thz_category"],
                current.thz_description != payload["thz_description"],
                current.thz_deduction != payload["thz_deduction"],
                current.severity != payload["severity"],
                current.challan_place != payload["challan_place"],
                current.challan_datetime != payload["challan_datetime"],
                current.state_code != payload["state_code"],
                current.rto != payload["rto"],
                current.accused_name != payload["accused_name"],
                current.fine_amount != payload["fine_amount"],
                current.challan_status != payload["challan_status"],
                current.court_challan != payload["court_challan"],
                current.court_name != payload["court_name"],
                current.upstream_code != payload["upstream_code"],
                current.active is not True,
                current.removed_at is not None,
            )
        )
    
    
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
            return await self._classify_with_openai(offense_details, offenses)
        return self._thz_from_code(best_code)


    async def _classify_with_openai(
        self,
        offense_details: str,
        offenses: list[str],
    ) -> THZCategoryMatch:
        allowed_categories = ", ".join(code.value for code in THZ_CATEGORY_PRIORITY)
        category_descriptions = "\n".join(
            f"- {code.value}: {THZ_CATEGORY_META[code].description}"
            for code in THZ_CATEGORY_PRIORITY
        )
        offenses_text = "\n".join(f"- {offense}" for offense in offenses) if offenses else "- None"
        prompt = (
            "You classify Indian traffic challans into one THZ category.\n"
            "Choose exactly one category from this list and return only that category string, nothing else:\n"
            f"{allowed_categories}\n\n"
            "THZ category descriptions:\n"
            f"{category_descriptions}\n\n"
            "Use both the challan offense_details and the offenses array.\n"
            "If there are multiple offenses, classify using the highest severity offense.\n\n"
            f"offense_details: {offense_details or 'None'}\n"
            f"offenses:\n{offenses_text}\n"
        )

        try:
            response = await self.openai_client.responses.create(
                model=self.OPENAI_CLASSIFICATION_MODEL,
                input=prompt,
                max_output_tokens=16,
            )
            raw_output = (response.output_text or "").strip()
            category = self._extract_thz_category(raw_output)
            if category is None:
                log_event(
                    self.logger,
                    "WARNING",
                    "challan.classify.openai_invalid_output",
                    output=raw_output,
                )
                return self._thz_from_code(THZCategory.THZ_12)

            log_event(
                self.logger,
                "INFO",
                "challan.classify.openai_success",
                category=category.value,
            )
            return self._thz_from_code(category)
        except Exception as exc:
            self.logger.exception(
                "event=challan.classify.openai_failed error=%s",
                str(exc),
            )
            return self._thz_from_code(THZCategory.THZ_12)


    def _extract_thz_category(self, value: str) -> THZCategory | None:
        normalized = value.strip().upper()
        for category in THZ_CATEGORY_PRIORITY:
            if normalized == category.value.upper():
                return category
        return None


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
            "offense_names": offenses,
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
