from datetime import datetime, timedelta

def needs_fetch(last_fetched_timestamp: datetime):
    return last_fetched_timestamp is None or datetime.now() - last_fetched_timestamp > timedelta(days=2)


def get_base_premium(
    score: int,
    vehicle_category: str,
    cubic_capacity: float,
):
    pass