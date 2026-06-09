from datetime import datetime


def get_min_fields_for_header(header: str) -> int | None:
    header_min_field_counts = {
        'DP': 31, # Data Packet
        'EPB': 16, # Emergency Data Packet
        'LI': 11, # Login Packet
        'HMP': 13 # Health Monitoring Packet
    }

    return header_min_field_counts.get(header)


def parse_dp_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse DP packet date (DDMMYYYY) and time (hhmmss) into a combined datetime."""
    try:
        return datetime.strptime(date_str + time_str, "%d%m%Y%H%M%S")
    except (ValueError, TypeError):
        return None


def parse_signed_coord(value_str: str, direction: str) -> float | None:
    """Convert a coordinate string and N/S/E/W direction into a signed float."""
    try:
        value = float(value_str)
    except (ValueError, TypeError):
        return None
    if direction in ('S', 'W'):
        value = -value
    return value


def safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_bool(value: str) -> bool | None:
    try:
        return bool(int(value))
    except (ValueError, TypeError):
        return None