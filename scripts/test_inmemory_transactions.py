"""Test script to validate the in-memory safe_execute_money_transaction fallback.

This script spawns concurrent tasks to simulate multiple simultaneous debit/credit
operations and verifies final balance. Run with the project's venv python.
"""
import asyncio
import sys
import pathlib

# Ensure repository root is on sys.path so imports work when running this script
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chronix_bot.utils import db


async def worker(uid: int, delta: int, times: int):
    for _ in range(times):
        await db.safe_execute_money_transaction(uid, delta, reason="test")


async def main():
    uid = 12345
    # reset store
    db._inmemory_store.clear()

    # schedule concurrent operations: 10 tasks adding 10, and 5 tasks subtracting 5
    tasks = []
    for _ in range(10):
        tasks.append(worker(uid, 10, 100))
    for _ in range(5):
        tasks.append(worker(uid, -5, 100))

    await asyncio.gather(*tasks)
    print("Final balance:", db._inmemory_store.get(uid))


if __name__ == "__main__":
    asyncio.run(main())
