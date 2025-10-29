import time
import pytest
from chronix_bot.utils import inventory


def _clear_file():
    f = inventory.INVENTORY_FILE
    if f.exists():
        f.unlink()


def test_add_merge_and_feed_pet():
    _clear_file()
    uid = 777
    # add gems
    g1 = inventory.add_gem(uid, "ruby", power=1)
    g2 = inventory.add_gem(uid, "ruby", power=2)
    g3 = inventory.add_gem(uid, "ruby", power=1)
    gems = inventory.list_gems(uid)
    assert len(gems) == 3
    # merge two gems
    new = inventory.merge_gems(uid, "ruby", count=2)
    assert new["gem_type"] == "ruby"
    assert new["power"] >= 2
    gems_after = inventory.list_gems(uid)
    assert len(gems_after) == 2  # consumed two, added one
    # pets
    pet = inventory.add_pet(uid, "fox")
    assert pet["species"] == "fox"
    pid = pet["pet_id"]
    fed = inventory.feed_pet(uid, pid, food_xp=120)
    assert fed["level"] >= 2
