import os
import json
import tempfile
import asyncio

from chronix_bot.utils import inventory_extras
from chronix_bot.utils import inventory


def test_remove_and_transfer_file_backed(tmp_path):
    # point data dir to temp to avoid polluting repo
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # create data dir
        (tmp_path / "data").mkdir()
        # add some items to user 1
        it = inventory.add_item(1, "Sword of Test", meta={"type": "weapon", "power": 5})
        assert it is not None
        item_id = it.get("item_id")
        assert item_id is not None

        # remove item
        removed = inventory_extras.remove_item(1, item_id)
        assert removed is not None
        assert removed.get("name") == "Sword of Test"

        # add another item and transfer it
        it2 = inventory.add_item(1, "Shield of Test", meta={"type": "armor", "def": 2})
        iid2 = it2.get("item_id")
        transferred = asyncio.get_event_loop().run_until_complete(inventory_extras.async_transfer_item(1, 2, iid2))
        assert transferred is not None
        # transferred has new item_id
        assert transferred.get("item_id") != iid2
        # ensure receiver has item
        items2 = inventory.list_items(2)
        assert any(i.get("name") == "Shield of Test" for i in items2)
    finally:
        os.chdir(orig_cwd)
