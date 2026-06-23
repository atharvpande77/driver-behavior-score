import os
import asyncpg

_pool: asyncpg.Pool | None = None


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url is None:
        raise RuntimeError("DATABASE_URL is not set")

    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def init_connection(conn) -> None:
    # Connection initialization and health validation
    await conn.execute("SELECT 1")


async def init_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_database_url(),
            min_size=1,
            max_size=5,
            command_timeout=5.0,
            timeout=5.0,
            init=init_connection,
        )

    return _pool


async def close_pool() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None



