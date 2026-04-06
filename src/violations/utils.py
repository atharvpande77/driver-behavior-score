import re
import unicodedata
from datetime import datetime, timedelta

from src.violations.constants import TTL_HOURS
from src.violations.types import THZCategory, ChallanSeverity


def none_if_blank(value: str | None):
    if value is None:
        return None
    value = value.strip()
    return value or None


_NON_WORD_SPACE_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_MULTI_SPACE_RE = re.compile(r"\s+")


def normalize_offense_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = _NON_WORD_SPACE_RE.sub(" ", normalized)
    normalized = _MULTI_SPACE_RE.sub(" ", normalized).strip()
    return normalized


def build_classification_corpus(offense_details: str | None, offenses: list[str]) -> str:
    parts = [normalize_offense_text(offense_details)]
    parts.extend(normalize_offense_text(offense) for offense in offenses)
    return _MULTI_SPACE_RE.sub(" ", " ".join(part for part in parts if part)).strip()


def needs_fetch(last_fetch_timestamp: datetime | None = None, ttl_hours: int = TTL_HOURS):
    if not last_fetch_timestamp:
        return True
    return datetime.now() - last_fetch_timestamp > timedelta(hours=ttl_hours)
    
    
def get_severity_from_thz_category(thz_category: THZCategory) -> str:
    if thz_category in {
        THZCategory.THZ_1,
        THZCategory.THZ_2,
        THZCategory.THZ_3,
    }:
        return ChallanSeverity.SEVERE

    if thz_category in {
        THZCategory.THZ_4,
        THZCategory.THZ_5,
        THZCategory.THZ_6,
        THZCategory.THZ_7,
        THZCategory.THZ_8,
        THZCategory.THZ_9,
        THZCategory.THZ_10,
    }:
        return ChallanSeverity.MODERATE

    return ChallanSeverity.LOW
