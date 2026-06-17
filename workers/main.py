import asyncio
import logging

from telematics.database import close_pool, init_pool
from workers.trips.repository import TripRepository
from workers.trips.service import TripService


logger = logging.getLogger(__name__)

DETECTOR_INTERVAL_SECONDS = 60


async def run_trip_detector(service: TripService) -> None:
    logger.info("Trip detector started (interval=%ds)", DETECTOR_INTERVAL_SECONDS)
    while True:
        try:
            await service.timeout_close_stale_open_trips()

            devices = await service.fetch_devices_with_new_events()

            if devices:
                logger.info("Detecting trips for %d device(s)", len(devices))

            for imei in devices:
                try:
                    await service.run_detector_for_device(imei)
                except Exception:
                    logger.exception("Trip detection failed for IMEI %s", imei)

        except Exception:
            logger.exception("Trip detector run failed")

        await asyncio.sleep(DETECTOR_INTERVAL_SECONDS)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    pool = await init_pool()
    logger.info("Worker pool initialised")

    repo = TripRepository(pool)
    service = TripService(repo)

    try:
        await asyncio.gather(
            run_trip_detector(service),
        )
    finally:
        await close_pool()
        logger.info("Worker pool closed")


if __name__ == "__main__":
    asyncio.run(main())
