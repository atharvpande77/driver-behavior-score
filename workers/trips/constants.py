"""Configuration constants for the trips worker."""

# Timeout threshold for silent devices to close an active trip automatically.
# If the time gap between consecutive telematics events exceeds this threshold
# (in seconds), the current trip is considered complete and is closed.
# This prevents dead or silent devices from keeping a single trip active for
# hours or days.
GAP_THRESHOLD_SECONDS: float = 1800.0  # 30 minutes

# The starting hour (inclusive) for classifying night-time driving.
# Hours are represented in 24-hour format [0-23].
NIGHT_START_HOUR: int = 20  # 20:00 (8:00 PM)

# The ending hour (exclusive) for classifying night-time driving.
# Hours are represented in 24-hour format [0-23].
# Together with NIGHT_START_HOUR, the night-time window is defined as [20:00, 05:00).
# Driving during this period is flagged as night driving for behavior scoring.
NIGHT_END_HOUR: int = 5  # 05:00 (5:00 AM)

# The minimum speed threshold (in km/h) to filter out GPS speed noise and idling.
# GPS speed values below this threshold are ignored for trip statistics and
# minimum speed calculations.
MIN_SPEED_THRESHOLD_KMPH: float = 2.0

# The threshold (in km) to detect odometer resets or anomalies.
# If the difference between consecutive odometer readings is negative or
# exceeds this value, it indicates an odometer reset or a telemetry jump,
# causing the distance calculation to fall back to GPS haversine formula.
ODOMETER_RESET_THRESHOLD_KM: float = 500.0

# The threshold (in km) below which a negative odometer delta is considered
# telemetry noise/rounding fluctuation rather than an actual odometer reset.
# Negative deltas within this threshold are treated as zero distance, avoiding
# unnecessary fallback to GPS haversine calculations.
ODOMETER_NOISE_THRESHOLD_KM: float = 1.0

# The maximum speed threshold (in km/h) to filter out highly distorted GPS speed noise.
# GPS speed values above this threshold are ignored for trip statistics and maximum speed calculations.
MAX_SPEED_THRESHOLD_KMPH: float = 150.0


