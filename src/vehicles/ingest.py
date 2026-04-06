import httpx
from datetime import date

from src.vehicles.types import NormalizedRC

from src.config import app_settings
from src.logging_utils import get_logger, log_event


class RCIngest:
    def __init__(self):
        self.source_id = "surepass_rc_v2"
        self.logger = get_logger(__name__)
        self.client = httpx.AsyncClient(
            base_url=app_settings.SUREPASS_BASE_URL,
            headers={"Authorization": app_settings.SUREPASS_API_KEY}
        )
        
        
    async def fetch(self, vehicle_number: str):
        log_event(self.logger, "INFO", "vehicle.fetch.start", vehicle_number=vehicle_number, source_id=self.source_id)
        try:
            response = await self.client.post(
                '/rc/rc-v2',
                data={
                    "id_number": vehicle_number,
                    "enrich": True
                }
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if 500 <= e.response.status_code < 600:
                self.logger.exception(
                    "event=vehicle.fetch.vendor_5xx vehicle_number=%s source_id=%s status_code=%s error=%s",
                    vehicle_number,
                    self.source_id,
                    e.response.status_code,
                    str(e),
                )
                return None
            self.logger.exception(
                "event=vehicle.fetch.failed vehicle_number=%s source_id=%s error=%s",
                vehicle_number,
                self.source_id,
                str(e),
            )
            raise
        except httpx.HTTPError as e:
            self.logger.exception(
                "event=vehicle.fetch.failed vehicle_number=%s source_id=%s error=%s",
                vehicle_number,
                self.source_id,
                str(e),
            )
            raise
        log_event(
            self.logger,
            "INFO",
            "vehicle.fetch.success",
            vehicle_number=vehicle_number,
            source_id=self.source_id,
            status_code=response.status_code,
        )
        
        raw_rc_data = response.json().get("data", {})
        return self._map(raw_rc_data)
        
        
    def _map(self, raw_rc_data: dict) -> NormalizedRC:
        def blank_to_none(value):
            if value is None:
                return None
            if isinstance(value, str) and not value.strip():
                return None
            return value

        def to_int(value):
            value = blank_to_none(value)
            if value is None:
                return None
            return int(float(value))

        def to_float(value):
            value = blank_to_none(value)
            if value is None:
                return None
            return float(value)

        def to_date(value):
            value = blank_to_none(value)
            if value is None:
                return None
            return date.fromisoformat(value)

        vehicle_number = blank_to_none(raw_rc_data.get("rc_number"))
        if vehicle_number is None:
            raise ValueError("rc_number is required in rc-v2 response")

        return NormalizedRC(
            source_id=self.source_id,
            vehicle_number=vehicle_number,
            state_code=vehicle_number[:2].upper(),
            category=blank_to_none(raw_rc_data.get("vehicle_category").upper()),
            category_description=blank_to_none(raw_rc_data.get("vehicle_category_description")),
            chassis_number=blank_to_none(raw_rc_data.get("vehicle_chasi_number")),
            engine_number=blank_to_none(raw_rc_data.get("vehicle_engine_number")),
            maker_description=blank_to_none(raw_rc_data.get("maker_description")),
            maker_model=blank_to_none(raw_rc_data.get("maker_model")),
            fit_up_to=to_date(raw_rc_data.get("fit_up_to")),
            manufacturing_date=blank_to_none(raw_rc_data.get("manufacturing_date_formatted"))
            or blank_to_none(raw_rc_data.get("manufacturing_date")),
            registration_date=to_date(raw_rc_data.get("registration_date")),
            registered_at=blank_to_none(raw_rc_data.get("registered_at")),
            body_type=blank_to_none(raw_rc_data.get("body_type")),
            fuel_type=blank_to_none(raw_rc_data.get("fuel_type")),
            norms_type=blank_to_none(raw_rc_data.get("norms_type")),
            color=blank_to_none(raw_rc_data.get("color")),
            cubic_capacity=to_float(raw_rc_data.get("cubic_capacity")),
            vehicle_gross_weight=to_int(raw_rc_data.get("vehicle_gross_weight")),
            no_cylinders=to_int(raw_rc_data.get("no_cylinders")),
            seat_capacity=to_int(raw_rc_data.get("seat_capacity")),
            sleeper_capacity=to_int(raw_rc_data.get("sleeper_capacity")),
            standing_capacity=to_int(raw_rc_data.get("standing_capacity")),
            wheelbase=to_int(raw_rc_data.get("wheelbase")),
            unladen_weight=to_int(raw_rc_data.get("unladen_weight")),
            owner_name=blank_to_none(raw_rc_data.get("owner_name")),
            present_address=blank_to_none(raw_rc_data.get("present_address")),
            permanent_address=blank_to_none(raw_rc_data.get("permanent_address")),
            mobile_number=blank_to_none(raw_rc_data.get("mobile_number")),
            financer=blank_to_none(raw_rc_data.get("financer")),
            financed=bool(raw_rc_data.get("financed", False)),
            insurance_company=blank_to_none(raw_rc_data.get("insurance_company")),
            insurance_policy_number=blank_to_none(raw_rc_data.get("insurance_policy_number")),
            pucc_number=blank_to_none(raw_rc_data.get("pucc_number")),
            pucc_upto=to_date(raw_rc_data.get("pucc_upto")),
            permit_number=blank_to_none(raw_rc_data.get("permit_number")),
            permit_issue_date=to_date(raw_rc_data.get("permit_issue_date")),
            permit_type=blank_to_none(raw_rc_data.get("permit_type")),
            national_permit_number=blank_to_none(raw_rc_data.get("national_permit_number")),
            national_permit_issued_by=blank_to_none(raw_rc_data.get("national_permit_issued_by")),
            blacklist_status=blank_to_none(raw_rc_data.get("blacklist_status")),
            noc_details=blank_to_none(raw_rc_data.get("noc_details")),
            owner_number=to_int(raw_rc_data.get("owner_number")),
            rc_status=blank_to_none(raw_rc_data.get("rc_status")),
            rto_code=blank_to_none(raw_rc_data.get("rto_code")),
        )
