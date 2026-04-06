import re


_VEHICLE_NUMBER_PATTERN = re.compile(
    r"^(?:\d{2}BH\d{4}[A-Z]{0,2}|[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4})$"
)

def serialize_vehicle_number(vehicle_number: str) -> str:
    """Normalize Indian vehicle numbers into a canonical alphanumeric form.

    The function accepts BH-series plates, state plates, and Delhi plates in
    loosely formatted input such as ``mh 12 ab 1234`` or ``24-bh-1234-aa`` and
    returns an uppercase string with separators removed.
    """

    normalized = re.sub(r"[^A-Z0-9]", "", vehicle_number.upper().strip())
    if not normalized:
        raise ValueError("vehicle_number cannot be empty")

    if not _VEHICLE_NUMBER_PATTERN.fullmatch(normalized):
        raise ValueError(f"Unsupported vehicle number format: {vehicle_number!r}")

    return normalized.upper()


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
