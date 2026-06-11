from datetime import datetime
import ctypes


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


def crc32_ais140(msg: str) -> int:
    """Python port of the C CRC32Bit function used in AIS-140 devices.

    Processes bytes at indices 1 through len(msg)-1 (i.e. skips the first
    character, which is the leading '$', and processes up to and including
    the last character).
    Polynomial: 0xEDB88320 (reversed CRC-32/ISO-HDLC).
    Returns the 32-bit unsigned CRC value.
    """
    crc = ctypes.c_uint32(0xFFFFFFFF)
    for ch in msg[1:]:
        byte = ord(ch)
        crc.value ^= byte
        for _ in range(8):
            mask = ctypes.c_int32(-(crc.value & 1)).value  # signed mask: 0 or 0xFFFFFFFF
            crc.value = (crc.value >> 1) ^ (0xEDB88320 & mask)
    return (~crc.value) & 0xFFFFFFFF


def compute_checksum_matched(raw_packet: str, received_checksum: str | None) -> bool | None:
    """Compute the AIS-140 CRC-32 over *raw_packet* and compare it against
    *received_checksum* (the hex string stored in the last packet field).

    Returns True/False on match/mismatch, or None if *received_checksum* is
    absent or cannot be parsed.
    """
    if not received_checksum:
        return None
    try:
        expected = int(received_checksum, 16)
    except ValueError:
        return None
    computed = crc32_ais140(raw_packet)
    return computed == expected