import asyncio
import logging
from contextlib import suppress

from telematics.database import close_pool, init_pool, store_raw_packet


HOST = "0.0.0.0"
PORT = 8002
READ_SIZE_BYTES = 4096

logger = logging.getLogger(__name__)


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    peername = writer.get_extra_info("peername")
    logger.info("Telematics client connected: %s", peername)

    try:
        while packet := await reader.read(READ_SIZE_BYTES):
            await store_raw_packet(packet)
    except Exception:
        logger.exception("Telematics client handling failed: %s", peername)
    finally:
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()
        logger.info("Telematics client disconnected: %s", peername)


async def run_server() -> None:
    await init_pool()

    server = await asyncio.start_server(handle_client, HOST, PORT)
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