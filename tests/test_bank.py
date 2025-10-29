import pytest

from chronix_bot.utils import db, interest


@pytest.mark.asyncio
async def test_deposit_withdraw_interest_cycle():
    db._inmemory_store.clear()
    db._inmemory_store[123] = 1000

    # Simulate deposit by moving money out of on-hand and into banks.json
    from chronix_bot.cogs.economy.bank import _write_banks
    banks = {"123": 0}
    await _write_banks(banks)

    # deposit 500
    from chronix_bot.utils import db as _db
    new_bal = await _db.safe_execute_money_transaction(123, -500, "test deposit")
    assert new_bal == 500

    # update banks file (simulate bank.deposit flow)
    banks = {"123": 500}
    await _write_banks(banks)

    # apply interest 1% -> 5
    updated = await interest.apply_interest(rate_percent=1.0)
    assert updated >= 1
