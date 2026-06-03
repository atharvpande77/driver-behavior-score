import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


_pool: asyncpg.Pool | None = None
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_PATH)


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url is None:
        raise RuntimeError("DATABASE_URL is not set")

    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def init_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_database_url(),
            min_size=3,
            max_size=3,
        )

    return _pool


async def close_pool() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


async def store_raw_packet(
    packet: bytes,
    source_ip: str | None = None,
    source_port: int | None = None,
) -> None:
    pool = await init_pool()
    raw_packet = packet.decode("utf-8", errors="replace").replace("\x00", "\\x00")

    await pool.execute(
        """
        INSERT INTO telematics_events (raw_packet, source_ip, source_port)
        VALUES ($1, $2, $3)
        """,
        raw_packet,
        source_ip,
        source_port,
    )
