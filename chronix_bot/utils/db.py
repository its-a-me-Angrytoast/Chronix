"""Database helper stubs for Chronix.

Phase 0: provide an async pool factory and simple helpers. This file is a
lightweight stub — we'll replace with a full asyncpg implementation in Phase 2.
"""
from typing import Optional, AsyncIterator
import asyncio
import contextlib

try:
    import asyncpg
except Exception:  # pragma: no cover - optional dependency in dev
    asyncpg = None  # type: ignore

_pool = None


async def init_pool(dsn: Optional[str] = None):
    """Initialize a DB pool if asyncpg is available and DSN is provided.

    Returns the pool instance or None when not configured.
    """
    global _pool
    if _pool is not None:
        return _pool
    if asyncpg is None or not dsn:
        return None
    _pool = await asyncpg.create_pool(dsn)
    return _pool


def get_pool():
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@contextlib.asynccontextmanager
async def transaction():
    """A simple transaction context manager for Phase 0.

    If a real pool is available it yields a connection/transaction, otherwise
    it yields a dummy object for in-memory testing.
    """
    pool = get_pool()
    if pool is None:
        # Provide a dummy context for dev
        class Dummy:
            async def execute(self, *a, **k):
                return None

            async def fetchrow(self, *a, **k):
                return None

        yield Dummy()
        return

    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise


async def safe_execute_money_transaction(user_id: int, delta: int, reason: str):
    """Phase 0 stub for atomic money transactions.

    This should be implemented properly in Phase 2 with SELECT ... FOR UPDATE
    semantics. For now it raises NotImplementedError to avoid accidental use.
    """
    raise NotImplementedError("safe_execute_money_transaction is not implemented in Phase 0")
