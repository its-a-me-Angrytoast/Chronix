import asyncio
import pytest

import sys
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chronix_bot.cogs.economy.economy import Economy
from chronix_bot.utils import db


@pytest.mark.asyncio
async def test_inmemory_transfer_simple():
    # reset store
    db._inmemory_store.clear()
    db._inmemory_store[1] = 1000
    db._inmemory_store[2] = 0

    cog = Economy(bot=None)  # bot is not used for _transfer in-memory
    new_bal = await cog._transfer(1, 2, 250)
    assert new_bal == 750
    assert db._inmemory_store[2] == 250


@pytest.mark.asyncio
async def test_inmemory_transfer_concurrent():
    db._inmemory_store.clear()
    uid = 42
    db._inmemory_store[uid] = 10000

    cog = Economy(bot=None)

    async def task():
        # transfer 10 units to user 99, repeated 100 times
        for _ in range(100):
            await cog._transfer(uid, 99, 10)

    tasks = [asyncio.create_task(task()) for _ in range(5)]
    await asyncio.gather(*tasks)

    # expected deduction: 5 * 100 * 10 = 5000
    assert db._inmemory_store[uid] == 5000
    assert db._inmemory_store[99] == 5000
