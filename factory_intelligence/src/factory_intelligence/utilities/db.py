"""
Async database connection pool using psycopg3.
"""

from psycopg_pool import AsyncConnectionPool

from factory_intelligence.database.config import DATABASE_URL

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(conninfo=DATABASE_URL, min_size=2, max_size=10)
        await _pool.open()
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
