import pytest

from chronix_bot.utils import db


@pytest.mark.asyncio
async def test_safe_execute_gambling_win_and_loss():
    # use in-memory fallback
    uid = 999999
    # reset store
    db._inmemory_store.clear()
    db._inmemory_store[uid] = 1000

    # simulate losing 200
    new_bal = await db.safe_execute_money_transaction(uid, -200, "test lose")
    assert new_bal == 800

    # simulate winning 500
    new_bal = await db.safe_execute_money_transaction(uid, 500, "test win")
    assert new_bal == 1300
