import httpx
from datetime import datetime
from abc import ABC, abstractmethod
import time

from src.violations.types import (
    NormalizedChallan,
    NormalizedChallanFetchResult,
    NormalizedChallanOffenseDetail,
)

from src.config import app_settings


# Later, use this base class to implement other providers like MahaTraffic, etc. For now, we only have Surepass, so we can keep it simple and directly implement the ingest logic there. But this structure allows us to easily add more providers in the future without changing the service layer.

class BaseChallanProvider(ABC):
    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique slug identifying this source. e.g. 'surepass_challan_advanced', 'maha_traffic'"""
 
    @abstractmethod
    async def fetch(self, vehicle_number: str) -> NormalizedChallanFetchResult:
        """
        Fetch all challans for a vehicle and return in normalized shape.
        Must raise ProviderException on any failure — never return partial data silently.
        """
    
    
class SurepassChallanAdvanced(BaseChallanProvider):
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.source_id = "surepass_challan_advanced"
    
    async def fetch(self, vehicle_number: str):
        pass

# Add more like class MahaTraffic(BaseChallanProvider): ...



class ChallanIngest:
    MAX_ERROR_INFO_LENGTH = 512

    def __init__(self, client: httpx.AsyncClient):
        self.source_id = "surepass_v1_challan_advanced"
        self.client = client

    def _truncate_error_info(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) <= self.MAX_ERROR_INFO_LENGTH:
            return value
        return value[: self.MAX_ERROR_INFO_LENGTH - 3] + "..."

    def _extract_error_info(self, exc: httpx.HTTPError) -> str | None:
        response = getattr(exc, "response", None)
        if response is None:
            return self._truncate_error_info(str(exc) or None)

        try:
            payload = response.json()
            if isinstance(payload, dict):
                return self._truncate_error_info(
                    payload.get("message")
                    or payload.get("detail")
                    or payload.get("error")
                    or str(payload)
                )
            return self._truncate_error_info(str(payload))
        except ValueError:
            return self._truncate_error_info(response.text or str(exc) or None)

    async def fetch(self, vehicle_number: str) -> NormalizedChallanFetchResult:
        start = time.perf_counter()
        try:
            response = await self.client.post(
                f"{app_settings.SUREPASS_BASE_URL}/rc/rc-related/challan-advanced",
                data={
                    "rc_number": vehicle_number
                },
                headers={
                    "Authorization": app_settings.SUREPASS_API_KEY
                }
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            return NormalizedChallanFetchResult(
                source_id=self.source_id,
                challans=[],
                vendor_latency_ms=(time.perf_counter() - start) * 1000,
                challan_fetch_failed=True,
                challan_error_info=self._extract_error_info(e),
            )
        except httpx.HTTPError as e:
            return NormalizedChallanFetchResult(
                source_id=self.source_id,
                challans=[],
                vendor_latency_ms=(time.perf_counter() - start) * 1000,
                challan_fetch_failed=True,
                challan_error_info=self._extract_error_info(e),
            )

        duration_ms = (time.perf_counter() - start) * 1000

        challans = response.json().get("data", {}).get("challan_details", [])
        return NormalizedChallanFetchResult(
            source_id=self.source_id,
            challans=[self._map(challan) for challan in challans],
            vendor_latency_ms=duration_ms,
            challan_fetch_failed=False,
            challan_error_info=None,
        )
        
        
    def _map(self, raw_data: dict) -> NormalizedChallan:
        amount = raw_data.get("amount")
        fine_amount = None
        if amount not in (None, ""):
            try:
                fine_amount = int(amount)
            except (TypeError, ValueError):
                fine_amount = None

        challan_datetime_raw = raw_data.get("challan_date_time") or raw_data.get("challan_datetime")
        if challan_datetime_raw is None:
            challan_datetime = datetime.fromisoformat(f"{raw_data['challan_date']}T00:00:00")
        else:
            challan_datetime = datetime.fromisoformat(challan_datetime_raw)

        offenses = [
            NormalizedChallanOffenseDetail(offense_name=offense.get("offense_name", ""))
            for offense in raw_data.get("offense_details_list", [])
            if offense.get("offense_name")
        ]

        return NormalizedChallan(
            number=raw_data["number"],
            challan_number=raw_data["challan_number"],
            source_id=self.source_id,
            offense_details=raw_data["offense_details"],
            offenses=offenses,
            challan_datetime=challan_datetime,
            state_code=raw_data["state"],
            court_challan=raw_data["court_challan"],
            challan_place=raw_data.get("challan_place") or None,
            accused_name=raw_data.get("accused_name") or None,
            rto=raw_data.get("rto") or None,
            fine_amount=fine_amount,
            challan_status=raw_data.get("challan_status") or None,
            court_name=raw_data.get("court_name") or None,
            upstream_code=raw_data.get("upstream_code") or None,
        )
