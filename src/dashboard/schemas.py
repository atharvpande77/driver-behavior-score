from pydantic import BaseModel, ConfigDict, Field, model_serializer, field_validator
from datetime import datetime

from src.score.types import DBSWithPremium
from src.utils import get_state_name, get_challan_paid_status, serialize_vehicle_number


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    vehicle_number: str
    category: str | None
    category_description: str | None
    state_code: str | None
    state_name: str | None = None
    fuel_type: str | None
    cc: float | None = Field(default=None, validation_alias="cubic_capacity")

    @model_serializer(mode="wrap")
    def add_state_name(self, handler):
        data = handler(self)
        data["state_name"] = get_state_name(self.state_code)
        return data
    
    
class THZCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    deduction: int


class ChallanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    challan_details: str = Field(validation_alias="challan_number")
    challan_date: datetime = Field(validation_alias="challan_datetime")
    fine_amount: int | None
    paid_status: bool = False
    severity: str
    thz_category: THZCategoryResponse | None = Field(
        default=None,
        exclude=True,
        validation_alias="__thz_category_ignored__",
    )
    thz_category_name: str | None = Field(validation_alias="thz_category", exclude=True)
    thz_category_description: str | None = Field(validation_alias="thz_description", exclude=True)
    thz_category_deduction: int | None = Field(validation_alias="thz_deduction", exclude=True)
    challan_status: str | None = Field(default=None, exclude=True)

    @model_serializer(mode="wrap")
    def add_derived_fields(self, handler):
        data = handler(self)
        data["paid_status"] = get_challan_paid_status(self.challan_status)
        if (
            self.thz_category_name is None
            or self.thz_category_description is None
            or self.thz_category_deduction is None
        ):
            data["thz_category"] = None
        else:
            data["thz_category"] = {
                "name": self.thz_category_name,
                "description": self.thz_category_description,
                "deduction": self.thz_category_deduction,
            }
        data.pop("thz_category_name", None)
        data.pop("thz_category_description", None)
        data.pop("thz_category_deduction", None)
        data.pop("challan_status", None)
        return data


class VehicleLookupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    violations: list[ChallanListResponse]
    dbs: DBSWithPremium
    vehicle: VehicleResponse
    fresh_as_of: datetime
    queried_at: datetime


class BatchVehicleLookupRequest(BaseModel):
    vehicle_numbers: list[str] = Field(min_length=1, max_length=50)

    @field_validator("vehicle_numbers")
    @classmethod
    def normalize_and_dedupe_vehicle_numbers(cls, vehicle_numbers: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()

        for vehicle_number in vehicle_numbers:
            normalized = serialize_vehicle_number(vehicle_number)
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)

        if not deduped:
            raise ValueError("At least one valid unique vehicle number is required")

        return deduped


class BatchVehicleLookupItem(BaseModel):
    vehicle_number: str
    category: str | None
    category_description: str | None
    score: int
    risk_level: str
    premium_modifier_pct: int
    total_violations: int


class BatchVehicleLookupResponse(BaseModel):
    results: list[BatchVehicleLookupItem]
    total_results: int
    risk_category_counts: dict[str, int]
