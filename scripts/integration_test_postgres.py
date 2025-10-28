"""Integration test: run against a real Postgres instance.

This script expects the Postgres DSN to be provided via the DATABASE_DSN
environment variable (see `.env.example`). It will initialize the asyncpg
pool, then execute a few `safe_execute_money_transaction` calls to verify
the DB-backed behavior.

Usage:
    DATABASE_DSN=postgres://chronix:chronixpass@localhost:5432/chronix \
      ./chronix.venv/bin/python scripts/integration_test_postgres.py
"""
import asyncio
import os
import sys
import pathlib

# Ensure repo root on path
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chronix_bot.utils import db


async def run_test():
    dsn = os.getenv("DATABASE_DSN")
    if not dsn:
        print("DATABASE_DSN must be set (e.g. postgres://chronix:chronixpass@postgres:5432/chronix)")
        return 2

    print("Initializing DB pool with DSN:", dsn)
    await db.init_pool(dsn)

    user_id = 999999
    print("Resetting user row (if any)")
    # clean previous state if present
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

    print("Performing transactions: +100, -30, +50")
    new = await db.safe_execute_money_transaction(user_id, 100, "integration: credit")
    print("Balance after +100:", new)
    new = await db.safe_execute_money_transaction(user_id, -30, "integration: debit")
    print("Balance after -30:", new)
    new = await db.safe_execute_money_transaction(user_id, 50, "integration: credit")
    print("Balance after +50:", new)

    # final check
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
        print("Final balance in DB:", row["balance"]) if row else print("No user row found")

    await db.close_pool()
    return 0


if __name__ == "__main__":
    code = asyncio.run(run_test())
    raise SystemExit(code)
