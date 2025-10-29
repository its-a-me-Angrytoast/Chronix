import pytest

from chronix_bot.utils import db


@pytest.mark.asyncio
async def test_marketplace_buy_and_list():
    db._inmemory_store.clear()
    buyer = 8001
    seller = 8002
    db._inmemory_store[buyer] = 1000
    db._inmemory_store[seller] = 0

    # create a fake listing file
    from chronix_bot.cogs.economy.marketplace import _write_market
    listings = [{"id": 1, "seller_id": seller, "item": "Test Sword", "price": 300}]
    await _write_market(listings)

    # simulate buyer pays (safe_execute_money_transaction)
    new_bal = await db.safe_execute_money_transaction(buyer, -300, "test buy")
    assert new_bal == 700
    new_bal2 = await db.safe_execute_money_transaction(seller, 300, "test sell")
    assert new_bal2 == 300
