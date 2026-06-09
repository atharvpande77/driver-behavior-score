import asyncio
import logging
import ipaddress
from contextlib import suppress
from functools import partial

from telematics.database import close_pool, init_pool
from telematics.service import TelematicsService


HOST = "0.0.0.0"
PORT = 8002
READ_SIZE_BYTES = 4096

logger = logging.getLogger(__name__)


def _is_loopback_peer(peername: object) -> bool:
    if not isinstance(peername, tuple) or len(peername) < 2:
        return False

    host = peername[0]
    if not isinstance(host, str):
        return False

    with suppress(ValueError):
        return ipaddress.ip_address(host).is_loopback

    return False


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    service: TelematicsService,
) -> None:
    peername = writer.get_extra_info("peername")

    if _is_loopback_peer(peername):
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()
        return

    source_ip: str | None = None
    source_port: int | None = None

    if isinstance(peername, tuple) and len(peername) >= 2:
        source_ip = str(peername[0])
        source_port = int(peername[1])

    logger.info("Telematics client connected: %s", peername)

    try:
        while packet := await reader.read(READ_SIZE_BYTES):
            await service.process_packet(
                packet,
                source_ip=source_ip,
                source_port=source_port,
            )
    except Exception:
        logger.exception("Telematics client handling failed: %s", peername)
    finally:
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()
        logger.info("Telematics client disconnected: %s", peername)


async def run_server() -> None:
    pool = await init_pool()
    service = TelematicsService(pool)

    server = await asyncio.start_server(
        partial(handle_client, service=service), HOST, PORT
    )
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logger.info("Telematics listener started on %s", sockets)

    async with server:
        try:
            await server.serve_forever()
        finally:
            await close_pool()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_server())


if __name__ == "__main__":
    main()