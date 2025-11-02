from chronix_bot.utils import weapons


def test_create_and_durability_and_repair():
    owner = 999999
    w = weapons.create_weapon(owner, "Test Blade", wtype="sword", attack=10, slots=1)
    wid = int(w["weapon_id"])
    assert w.get("durability") == w.get("max_durability")
    # reduce
    ok = weapons.reduce_durability(owner, wid, amount=10)
    assert ok
    w2 = weapons.get_weapon(owner, wid)
    assert w2["durability"] == w.get("max_durability") - 10
    # repair and cost
    cost = weapons.repair_weapon(owner, wid)
    assert cost is not None
    w3 = weapons.get_weapon(owner, wid)
    assert w3["durability"] == w3["max_durability"]
