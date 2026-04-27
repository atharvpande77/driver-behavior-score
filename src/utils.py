import re


_BH_VEHICLE_NUMBER_PATTERN = re.compile(
    r"^(?P<year>\d{2})BH(?P<number>\d{4})(?P<suffix>[A-Z]{0,2})$"
)
_STATE_VEHICLE_NUMBER_PATTERN = re.compile(
    r"^(?P<state>[A-Z]{2})(?P<rto>\d{1,2})(?P<series>[A-Z]{1,3})(?P<number>\d{4})$"
)

_CURRENT_STATE_CODES = frozenset(
    {
        "AN",
        "AP",
        "AR",
        "AS",
        "BR",
        "CH",
        "CG",
        "DL",
        "DN",
        "GA",
        "GJ",
        "HR",
        "HP",
        "JH",
        "JK",
        "KA",
        "KL",
        "LA",
        "LD",
        "MH",
        "ML",
        "MN",
        "MP",
        "MZ",
        "NL",
        "OD",
        "PB",
        "PY",
        "RJ",
        "SK",
        "TN",
        "TS",
        "TR",
        "UK",
        "UP",
        "WB",
    }
)
_LEGACY_STATE_CODES = frozenset({"DD", "OR"})
_VALID_STATE_CODES = _CURRENT_STATE_CODES | _LEGACY_STATE_CODES


def serialize_vehicle_number(vehicle_number: str) -> str:
    """Normalize Indian vehicle numbers into a canonical alphanumeric form.

    The function accepts BH-series plates and standard state/UT registration
    marks in loosely formatted input such as ``mh 12 ab 1234`` or
    ``24-bh-1234-aa`` and returns an uppercase string with separators removed.
    """

    normalized = re.sub(r"[^A-Z0-9]", "", vehicle_number.upper().strip())
    if not normalized:
        raise ValueError("vehicle_number cannot be empty")

    bh_match = _BH_VEHICLE_NUMBER_PATTERN.fullmatch(normalized)
    if bh_match:
        return normalized

    state_match = _STATE_VEHICLE_NUMBER_PATTERN.fullmatch(normalized)
    if state_match and state_match.group("state") in _VALID_STATE_CODES:
        return normalized

    if len(normalized) >= 2 and normalized[:2].isalpha() and normalized[:2] not in _VALID_STATE_CODES:
        raise ValueError(
            f"Unsupported state code in vehicle number: {vehicle_number!r}"
        )

    if not (bh_match or state_match):
        raise ValueError(f"Unsupported vehicle number format: {vehicle_number!r}")

    return normalized


STATE_NAME_MAP: dict[str, str] = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "DL": "Delhi",
    "DN": "Dadra and Nagar Haveli and Daman and Diu",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "JK": "Jammu and Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
}


def get_state_name(state_code: str | None) -> str | None:
    if not state_code:
        return None

    normalized = state_code.strip().upper()
    return STATE_NAME_MAP.get(normalized, normalized)


def get_challan_paid_status(challan_status: str | None) -> bool:
    if not challan_status:
        return False

    normalized = challan_status.strip().casefold()
    return normalized in {
        "paid",
        "payment done",
        "payment completed",
        "closed",
        "closed paid",
        "resolved",
    }
