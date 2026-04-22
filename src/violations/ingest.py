import httpx
from datetime import datetime
from abc import ABC, abstractmethod

from src.violations.types import NormalizedChallan, NormalizedChallanOffenseDetail

from src.config import app_settings


# Later, use this base class to implement other providers like MahaTraffic, etc. For now, we only have Surepass, so we can keep it simple and directly implement the ingest logic there. But this structure allows us to easily add more providers in the future without changing the service layer.

class BaseChallanProvider(ABC):
    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique slug identifying this source. e.g. 'surepass_challan_advanced', 'maha_traffic'"""
 
    @abstractmethod
    async def fetch(self, vehicle_number: str) -> list[NormalizedChallan]:
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
    def __init__(self, client: httpx.AsyncClient):
        self.source_id = "surepass_v1_challan_advanced"
        self.client = client
        
        
    async def fetch(self, vehicle_number: str) -> tuple[str, list[NormalizedChallan]]:
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
        except httpx.HTTPError:
            raise
        
        challans = response.json().get("data", {}).get("challan_details", [])
        return self.source_id, [self._map(challan) for challan in challans]
        
        
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
