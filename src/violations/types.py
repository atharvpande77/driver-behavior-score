from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass
class NormalizedChallanOffenseDetail:
    offense_name: str

@dataclass
class NormalizedChallan:
    number: int
    challan_number: str
    source_id: str
    offense_details: str
    offenses: list[NormalizedChallanOffenseDetail]
    challan_datetime: datetime
    state_code: str
    court_challan: bool
    challan_place: str | None = None
    accused_name: str | None = None
    rto: str | None = None
    fine_amount: int | None = None
    challan_status: str | None = None
    court_name: str | None = None
    upstream_code: str | None = None
    
    
@dataclass
class THZCategoryMatch:
    category: str
    description: str
    deduction: int


@dataclass(kw_only=True)
class THZCategoryDTO:
    name: str
    description: str
    deduction: int


@dataclass(kw_only=True)
class ChallanDTO:
    challan_number: str
    challan_datetime: datetime
    fine_amount: int | None
    severity: str
    challan_place: str | None
    offense_details: str | None
    thz_category_name: str | None
    thz_category_description: str | None
    thz_category_deduction: int | None
    thz_deduction: int
    challan_status: str | None


class THZCategory(str, Enum):
    THZ_1 = "THZ 1"
    THZ_2 = "THZ 2"
    THZ_3 = "THZ 3"
    THZ_4 = "THZ 4"
    THZ_5 = "THZ 5"
    THZ_6 = "THZ 6"
    THZ_7 = "THZ 7"
    THZ_8 = "THZ 8"
    THZ_9 = "THZ 9"
    THZ_10 = "THZ 10"
    THZ_11 = "THZ 11"
    THZ_12 = "THZ 12"


class ChallanSeverity(str, Enum):
    SEVERE = "SEVERE"
    MODERATE = "MODERATE"
    LOW = "LOW"
