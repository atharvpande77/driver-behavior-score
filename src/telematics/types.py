from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class DateRangePreset(StrEnum):
    TODAY = "today"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


@dataclass
class ResolvedDateRange:
    start_dt: datetime
    end_dt: datetime
    range_label: str | None
    from_date: date
    to_date: date


@dataclass
class PaginationParams:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
