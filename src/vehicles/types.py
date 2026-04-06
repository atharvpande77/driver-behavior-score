from dataclasses import dataclass
from datetime import date


@dataclass(kw_only=True)
class NormalizedRC:
    source_id: str
    vehicle_number: str
    state_code: str | None
    category: str | None
    category_description: str | None
    chassis_number: str | None
    engine_number: str | None
    maker_description: str | None
    maker_model: str | None
    fit_up_to: date | None
    manufacturing_date: str | None
    registration_date: date | None
    registered_at: str | None
    body_type: str | None
    fuel_type: str | None
    norms_type: str | None = None
    color: str | None
    cubic_capacity: float | None
    vehicle_gross_weight: int | None
    no_cylinders: int | None
    seat_capacity: int | None
    sleeper_capacity: int | None
    standing_capacity: int | None
    wheelbase: int | None
    unladen_weight: int | None
    owner_name: str | None
    present_address: str | None
    permanent_address: str | None
    mobile_number: str | None
    financer: str | None = None
    financed: bool
    insurance_company: str | None = None
    insurance_policy_number: str | None = None
    pucc_number: str | None = None
    pucc_upto: date | None = None
    permit_number: str | None = None
    permit_issue_date: date | None = None
    permit_type: str | None = None
    national_permit_number: str | None = None
    national_permit_issued_by: str | None = None
    blacklist_status: str | None = None
    noc_details: str | None = None
    owner_number: int | None = None
    rc_status: str | None = None
    rto_code: str | None = None


@dataclass(kw_only=True)
class VehicleDTO:
    vehicle_number: str
    state_code: str | None
    category: str | None
    category_description: str | None
    maker_description: str | None
    maker_model: str | None
    body_type: str | None
    fuel_type: str | None
    color: str | None
    manufacturing_date: str | None
    cubic_capacity: float | None
    owner_name: str | None
    rto_code: str | None
