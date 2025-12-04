"""
Database connection and utilities for TimescaleDB
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import asyncpg
from asyncpg import Pool

from config.settings import db_config

logger = logging.getLogger(__name__)


class Database:
    """Async database connection pool for TimescaleDB"""

    _pool: Optional[Pool] = None

    @classmethod
    async def get_pool(cls) -> Pool:
        """Get or create connection pool"""
        if cls._pool is None:
            # Use DATABASE_URL if available (Railway), else use individual params
            if db_config.database_url:
                dsn = db_config.database_url.replace("postgres://", "postgresql://")
                cls._pool = await asyncpg.create_pool(
                    dsn=dsn,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                )
            else:
                cls._pool = await asyncpg.create_pool(
                    host=db_config.host,
                    port=db_config.port,
                    database=db_config.database,
                    user=db_config.user,
                    password=db_config.password,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                )
            logger.info("Database connection pool created")
        return cls._pool

    @classmethod
    async def close(cls):
        """Close connection pool"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")

    @classmethod
    @asynccontextmanager
    async def connection(cls):
        """Get a connection from pool"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    async def execute(cls, query: str, *args) -> str:
        """Execute a query"""
        async with cls.connection() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query: str, *args) -> List[asyncpg.Record]:
        """Fetch multiple rows"""
        async with cls.connection() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def fetchrow(cls, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch single row"""
        async with cls.connection() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetchval(cls, query: str, *args) -> Any:
        """Fetch single value"""
        async with cls.connection() as conn:
            return await conn.fetchval(query, *args)

    @classmethod
    async def executemany(cls, query: str, args: List[tuple]) -> None:
        """Execute query with multiple parameter sets"""
        async with cls.connection() as conn:
            await conn.executemany(query, args)


# Token and Exchange ID caches
_token_id_cache: Dict[str, int] = {}
_exchange_id_cache: Dict[str, int] = {}


async def get_token_id(symbol: str) -> Optional[int]:
    """Get token ID by symbol with caching"""
    if symbol not in _token_id_cache:
        token_id = await Database.fetchval(
            "SELECT id FROM fan_tokens WHERE symbol = $1", symbol
        )
        if token_id:
            _token_id_cache[symbol] = token_id
    return _token_id_cache.get(symbol)


async def get_exchange_id(code: str) -> Optional[int]:
    """Get exchange ID by code with caching"""
    if code not in _exchange_id_cache:
        exchange_id = await Database.fetchval(
            "SELECT id FROM exchanges WHERE code = $1", code
        )
        if exchange_id:
            _exchange_id_cache[code] = exchange_id
    return _exchange_id_cache.get(code)


async def get_all_tokens() -> List[Dict[str, Any]]:
    """Get all active Chiliz fan tokens (excludes Binance tokens)"""
    rows = await Database.fetch(
        """SELECT id, symbol, name, team, coingecko_id FROM fan_tokens
           WHERE is_active = TRUE
           AND symbol NOT IN ('SANTOS', 'LAZIO', 'PORTO', 'ALPINE')"""
    )
    return [dict(row) for row in rows]


async def get_all_exchanges() -> List[Dict[str, Any]]:
    """Get all active exchanges"""
    rows = await Database.fetch(
        "SELECT id, code, name, coingecko_id FROM exchanges WHERE is_active = TRUE ORDER BY priority"
    )
    return [dict(row) for row in rows]


async def init_db():
    """Initialize database and run migrations"""
    import os

    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")

    async with Database.connection() as conn:
        # Run migrations in order
        for filename in sorted(os.listdir(migrations_dir)):
            if filename.endswith(".sql"):
                filepath = os.path.join(migrations_dir, filename)
                with open(filepath, "r") as f:
                    sql = f.read()
                try:
                    await conn.execute(sql)
                    logger.info(f"Executed migration: {filename}")
                except Exception as e:
                    logger.warning(f"Migration {filename} warning: {e}")

    logger.info("Database initialized")
