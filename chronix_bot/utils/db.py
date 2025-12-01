"""Database helpers for Chronix (Phase 2).

This module provides a production-grade asyncpg pool factory, a reusable
transaction context manager, a SELECT ... FOR UPDATE helper, and an atomic
money transaction helper implementing SELECT FOR UPDATE semantics.

NOTE: This code assumes PostgreSQL and that the database contains the
`users` and `transactions` tables. Migrations are deferred to Phase 15 — for
now, operators should create those tables manually using `docs/schema.md`.
"""
from typing import Optional, AsyncIterator, Any
import contextlib
import logging
from datetime import datetime
import asyncio
import os
from pathlib import Path

import asyncpg

logger = logging.getLogger("chronix.db")

def get_db_url() -> str:
    """Get database URL from environment or use SQLite for development."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Use SQLite for development
        db_path = Path(__file__).parents[2] / "data" / "chronix.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
    return db_url

_pool: Optional[asyncpg.pool.Pool] = None

# In-memory fallback store for development when no Postgres pool is available.
# This allows Phase 3 development without a running Postgres instance.
_inmemory_store: dict[int, int] = {}
_inmemory_lock = asyncio.Lock()


async def init_pool(dsn: str, *, min_size: int = 1, max_size: int = 10) -> asyncpg.pool.Pool:
    """Initialize an asyncpg pool and return it.

    Args:
        dsn: PostgreSQL DSN, e.g. postgres://user:pass@host:5432/dbname
        min_size: pool minimum size
        max_size: pool maximum size
    """
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    logger.info("DB pool initialized (min=%s max=%s)", min_size, max_size)
    return _pool


def get_pool() -> Optional[asyncpg.pool.Pool]:
    """Return the active asyncpg pool or None if not initialized."""
    return _pool


async def close_pool() -> None:
    """Close the active pool if present."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@contextlib.asynccontextmanager
async def transaction(conn: Optional[asyncpg.Connection] = None) -> AsyncIterator[asyncpg.Connection]:
    """Context manager yielding a connection inside a transaction.

    If `conn` is provided it will start and commit/rollback a transaction on it.
    Otherwise it will acquire a connection from the module pool. Raises
    `RuntimeError` if the pool isn't initialized.
    """
    pool = get_pool()
    if conn is not None:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
        return

    if pool is None:
        raise RuntimeError("DB pool not initialized. Call init_pool(dsn) first.")

    async with pool.acquire() as connection:
        tx = connection.transaction()
        await tx.start()
        try:
            yield connection
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise


async def select_for_update(query: str, *params: Any) -> Optional[asyncpg.Record]:
    """Run a SELECT query with FOR UPDATE and return the first row.

    The provided `query` must be a SELECT statement (no trailing semicolon).
    This helper appends `FOR UPDATE` unless the query already ends with it.
    It runs inside a short transaction to ensure the row is locked.
    """
    pool = get_pool()
    if pool is None:
        raise RuntimeError("DB pool is not initialized. Cannot perform select_for_update")

    async with pool.acquire() as conn:
        async with conn.transaction():
            q = query.strip()
            if not q.lower().endswith("for update"):
                q = q + " FOR UPDATE"
            return await conn.fetchrow(q, *params)


async def safe_execute_money_transaction(user_id: int, delta: int, reason: str, *, pool: Optional[asyncpg.pool.Pool] = None) -> int:
    """Atomically change a user's balance and write a transactions row.

    Behavior:
    - Lock the user's row via SELECT ... FOR UPDATE
    - Create user row if missing (balance = 0)
    - Ensure balance does not go negative (raises RuntimeError)
    - Update balance and insert a transactions log row

    Returns the new balance after the operation.

    Note: This function expects `users(user_id bigint primary key, balance bigint, created_at timestamptz)`
    and `transactions(id serial primary key, user_id bigint, delta bigint, reason text, balance_after bigint, created_at timestamptz)` to exist.
    """
    used_pool = pool or get_pool()
    # If there's no pool, fall back to an in-memory store for development.
    if used_pool is None:
        async with _inmemory_lock:
            current = _inmemory_store.get(user_id, 0)
            new_balance = current + delta
            if new_balance < 0:
                raise RuntimeError("Insufficient funds")
            _inmemory_store[user_id] = new_balance
            # In-memory 'transactions' are not persisted; return new balance
            return new_balance

    async with used_pool.acquire() as conn:
        async with conn.transaction():
            # SELECT ... FOR UPDATE to lock the row
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", user_id)
            if row is None:
                current = 0
                await conn.execute("INSERT INTO users (user_id, balance, created_at) VALUES ($1, $2, $3)", user_id, 0, datetime.utcnow())
            else:
                current = row["balance"]

            new_balance = current + delta
            if new_balance < 0:
                raise RuntimeError("Insufficient funds")

            await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_balance, user_id)

            await conn.execute(
                "INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1, $2, $3, $4, $5)",
                user_id,
                delta,
                reason,
                new_balance,
                datetime.utcnow(),
            )

            return new_balance
