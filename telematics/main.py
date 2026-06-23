import asyncio
import ipaddress
import time
import socket
import signal
from contextlib import suppress
from functools import partial

from telematics.logging_utils import configure_logging, get_logger, log_event
from telematics.database import close_pool, init_pool
from telematics.service import TelematicsService


from telematics.constants import (
    HOST,
    PORT,
    HEALTH_HOST,
    HEALTH_PORT,
    READ_SIZE_BYTES,
    MAX_BUFFER_BYTES,
    CONNECTION_IDLE_TIMEOUT_SECONDS,
    MAX_PACKET_SIZE_BYTES,
    MAX_SIMULTANEOUS_CONNECTIONS,
    MAX_CONNECTION_LIFETIME_SECONDS,
    TCP_BACKLOG,
    MAX_PACKETS_PER_SECOND_PER_IP,
    MAX_PACKETS_PER_SECOND_PER_IMEI,
)

logger = get_logger(__name__)

# Active connection tracker (Semaphore)
active_connections_sem = asyncio.Semaphore(MAX_SIMULTANEOUS_CONNECTIONS)

# Active connection task set for connection draining
active_tasks = set()

# Graceful shutdown event
shutdown_event = asyncio.Event()


class TokenBucketRateLimiter:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.buckets = {}

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        tokens, last_update = self.buckets.get(key, (self.capacity, now))
        elapsed = now - last_update
        tokens = min(self.capacity, tokens + elapsed * self.rate)
        
        if tokens >= 1.0:
            self.buckets[key] = (tokens - 1.0, now)
            return True
        else:
            self.buckets[key] = (tokens, now)
            return False

    def prune(self) -> None:
        now = time.time()
        threshold = 300.0
        keys_to_delete = [
            k for k, (t, lu) in self.buckets.items()
            if now - lu > threshold
        ]
        for k in keys_to_delete:
            self.buckets.pop(k, None)


ip_limiter = TokenBucketRateLimiter(rate=MAX_PACKETS_PER_SECOND_PER_IP, capacity=MAX_PACKETS_PER_SECOND_PER_IP * 2)
imei_limiter = TokenBucketRateLimiter(rate=MAX_PACKETS_PER_SECOND_PER_IMEI, capacity=MAX_PACKETS_PER_SECOND_PER_IMEI * 2)


async def prune_rate_limiters_periodically() -> None:
    while True:
        await asyncio.sleep(300)  # prune every 5 minutes
        ip_limiter.prune()
        imei_limiter.prune()


def is_valid_encoding(packet_str: str) -> bool:
    # Reject replacement characters (indicating decode failure)
    if "\ufffd" in packet_str:
        return False
    # Standard printable ASCII (32 to 126) and CR, LF
    for char in packet_str:
        o = ord(char)
        if not (32 <= o < 127 or char in "\r\n"):
            return False
    return True


def _is_loopback_peer(peername: object) -> bool:
    if not isinstance(peername, tuple) or len(peername) < 2:
        return False

    host = peername[0]
    if not isinstance(host, str):
        return False

    with suppress(ValueError):
        return ipaddress.ip_address(host).is_loopback

    return False


def configure_tcp_keepalive(writer: asyncio.StreamWriter) -> None:
    sock = writer.get_extra_info("socket")
    if sock is not None:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 300)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 60)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
        except Exception as e:
            logger.debug("Failed to set TCP keepalive options: %s", e)


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

    # Check maximum simultaneous connections
    if active_connections_sem.locked():
        log_event(logger, "WARNING", "telematics.server.max_connections_reached", peername=str(peername))
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()
        return

    # Register current task for tracking connection draining
    current_task = asyncio.current_task()
    if current_task:
        active_tasks.add(current_task)

    try:
        async with active_connections_sem:
            source_ip: str | None = None
            source_port: int | None = None

            if isinstance(peername, tuple) and len(peername) >= 2:
                source_ip = str(peername[0])
                source_port = int(peername[1])

            configure_tcp_keepalive(writer)
            log_event(logger, "INFO", "telematics.client.connected", source_ip=source_ip, source_port=source_port)

            connection_start_time = time.time()
            packets_processed = 0
            errors_encountered = 0

            try:
                buf = ""
                while True:
                    # Check graceful shutdown signal
                    if shutdown_event.is_set():
                        log_event(logger, "INFO", "telematics.client.draining", peername=str(peername))
                        break

                    # Connection lifetime check
                    if time.time() - connection_start_time > MAX_CONNECTION_LIFETIME_SECONDS:
                        log_event(logger, "INFO", "telematics.client.lifetime_exceeded", peername=str(peername))
                        break

                    # Connection idle timeout
                    try:
                        async with asyncio.timeout(CONNECTION_IDLE_TIMEOUT_SECONDS):
                            chunk = await reader.read(READ_SIZE_BYTES)
                    except TimeoutError:
                        log_event(logger, "WARNING", "telematics.client.idle_timeout", peername=str(peername))
                        errors_encountered += 1
                        break

                    if not chunk:
                        break

                    buf += chunk.decode("utf-8", errors="replace")

                    # Discard any garbage arriving before the first packet start marker
                    start = buf.find("$")
                    if start == -1:
                        buf = ""
                        continue
                    if start > 0:
                        buf = buf[start:]

                    # Extract every complete $ ... * packet present in the buffer
                    while True:
                        end = buf.find("*")
                        if end == -1:
                            break  # incomplete packet — wait for more data

                        packet_str = buf[: end + 1]  # includes trailing *
                        buf = buf[end + 1 :]         # keep remainder for next iteration

                        # Maximum packet size protection
                        if len(packet_str) > MAX_PACKET_SIZE_BYTES:
                            log_event(
                                logger, "WARNING", "telematics.packet.oversized",
                                packet_size=len(packet_str),
                                peername=str(peername)
                            )
                            errors_encountered += 1
                            return

                        # Input character/encoding validation
                        if not is_valid_encoding(packet_str):
                            log_event(
                                logger, "WARNING", "telematics.packet.invalid_encoding",
                                peername=str(peername)
                            )
                            errors_encountered += 1
                            return

                        # Rate limiting by IP
                        if source_ip and not ip_limiter.is_allowed(source_ip):
                            log_event(
                                logger, "WARNING", "telematics.rate_limit.ip_exceeded",
                                source_ip=source_ip
                            )
                            errors_encountered += 1
                            continue

                        # Rate limiting by IMEI
                        fields = packet_str[1:-1].split(',')
                        if len(fields) > 6 and fields[0] == 'DP':
                            imei = fields[6]
                            if imei and not imei_limiter.is_allowed(imei):
                                log_event(
                                    logger, "WARNING", "telematics.rate_limit.imei_exceeded",
                                    imei=imei,
                                    source_ip=source_ip
                                )
                                errors_encountered += 1
                                continue

                        try:
                            await service.process_packet(
                                packet_str,
                                source_ip=source_ip,
                                source_port=source_port,
                            )
                            packets_processed += 1
                        except Exception as e:
                            logger.error("Error processing packet from %s: %s", peername, e)
                            errors_encountered += 1

                        # Trim any garbage before the next packet start marker
                        next_start = buf.find("$")
                        if next_start == -1:
                            buf = ""
                            break
                        if next_start > 0:
                            buf = buf[next_start:]

                    # Safety valve: disconnect runaway connections
                    if len(buf) > MAX_BUFFER_BYTES:
                        log_event(
                            logger, "WARNING", "telematics.client.buffer_overflow",
                            buffer_size=len(buf),
                            peername=str(peername)
                        )
                        errors_encountered += 1
                        break
            except Exception as e:
                logger.exception("Telematics client loop exception: %s", e)
            finally:
                log_event(
                    logger, "INFO", "telematics.client.disconnected",
                    source_ip=source_ip,
                    source_port=source_port,
                    packets_processed=packets_processed,
                    errors_encountered=errors_encountered
                )
                writer.close()
                with suppress(ConnectionError):
                    await writer.wait_closed()
    finally:
        if current_task:
            active_tasks.discard(current_task)


def handle_shutdown_signal(sig_name: str) -> None:
    log_event(logger, "INFO", "telematics.server.signal_received", signal=sig_name)
    shutdown_event.set()


async def handle_health_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, pool: asyncio.StreamWriter | None) -> None:
    try:
        request_line = await reader.readline()
        parts = request_line.decode('utf-8', errors='ignore').split()
        if len(parts) >= 2 and parts[0] == 'GET':
            path = parts[1]
            if path == '/live':
                body = "OK"
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/plain\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                    f"{body}"
                )
            elif path == '/ready':
                db_ok = False
                if pool is not None:
                    try:
                        async with asyncio.timeout(2.0):
                            await pool.execute("SELECT 1")
                        db_ok = True
                    except Exception:
                        pass
                
                accepting = not shutdown_event.is_set()

                if db_ok and accepting:
                    body = "READY"
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "Connection: close\r\n\r\n"
                        f"{body}"
                    )
                else:
                    body = "SERVICE UNAVAILABLE"
                    status = "503 Service Unavailable"
                    response = (
                        f"HTTP/1.1 {status}\r\n"
                        "Content-Type: text/plain\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "Connection: close\r\n\r\n"
                        f"{body}"
                    )
            else:
                body = "NOT FOUND"
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: text/plain\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                    f"{body}"
                )
        else:
            body = "BAD REQUEST"
            response = (
                "HTTP/1.1 400 Bad Request\r\n"
                "Content-Type: text/plain\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
                f"{body}"
            )
        
        writer.write(response.encode('utf-8'))
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()


async def run_server() -> None:
    pool = await init_pool()
    service = TelematicsService(pool)

    # Start the rate limiter pruning task
    prune_task = asyncio.create_task(prune_rate_limiters_periodically())

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, partial(handle_shutdown_signal, sig.name))

    # Start loopback internal health server
    health_server = await asyncio.start_server(
        partial(handle_health_client, pool=pool), HEALTH_HOST, HEALTH_PORT
    )
    log_event(logger, "INFO", "telematics.health_server.started", host=HEALTH_HOST, port=HEALTH_PORT)

    # Start main listener server
    server = await asyncio.start_server(
        partial(handle_client, service=service), HOST, PORT, backlog=TCP_BACKLOG
    )
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    log_event(logger, "INFO", "telematics.server.started", sockets=sockets)

    # Keep running until the shutdown event triggers
    await shutdown_event.wait()

    log_event(logger, "INFO", "telematics.server.shutting_down")
    
    # Stop accepting new connections
    server.close()
    await server.wait_closed()
    
    health_server.close()
    await health_server.wait_closed()

    # Drain active connection tasks
    DRAIN_TIMEOUT = 10.0
    current_task = asyncio.current_task()
    tasks_to_drain = [t for t in active_tasks if t is not current_task]
    if tasks_to_drain:
        log_event(logger, "INFO", "telematics.server.draining_tasks", count=len(tasks_to_drain))
        try:
            async with asyncio.timeout(DRAIN_TIMEOUT):
                await asyncio.gather(*tasks_to_drain, return_exceptions=True)
        except TimeoutError:
            log_event(logger, "WARNING", "telematics.server.drain_timeout")
            for t in tasks_to_drain:
                t.cancel()
            with suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks_to_drain, return_exceptions=True)

    # Stop rate limiter pruning
    prune_task.cancel()
    with suppress(asyncio.CancelledError):
        await prune_task

    # Close DB pool
    log_event(logger, "INFO", "telematics.database.closing_pool")
    await close_pool()
    log_event(logger, "INFO", "telematics.server.shutdown_complete")


def main() -> None:
    configure_logging()
    asyncio.run(run_server())


if __name__ == "__main__":
    main()