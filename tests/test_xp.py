import asyncio
import os
import tempfile
import json

import pytest

from chronix_bot.utils import xp as xp_utils


@pytest.mark.asyncio
async def test_level_math():
    # base default 100
    assert xp_utils.xp_for_level(0) == 0
    assert xp_utils.xp_for_level(1) == 100
    assert xp_utils.xp_for_level(2) == 400
    assert xp_utils.level_from_xp(0) == 0
    assert xp_utils.level_from_xp(100) == 1
    assert xp_utils.level_from_xp(399) == 1
    assert xp_utils.level_from_xp(400) == 2


@pytest.mark.asyncio
async def test_add_xp_and_levelup(tmp_path):
    # use temp files by monkeypatching DATA_DIR
    orig_data_dir = xp_utils.DATA_DIR
    try:
        xp_utils.DATA_DIR = tmp_path
        # ensure files
        await xp_utils._write_json(xp_utils.XP_FILE, {})
        res = await xp_utils.add_xp(1, 42, 150)
        assert res["old_xp"] == 0
        assert res["new_xp"] == 150
        assert res["leveled"] is True
        assert res["new_level"] == xp_utils.level_from_xp(150)
        # adding small amount shouldn't level
        res2 = await xp_utils.add_xp(1, 42, 10)
        assert res2["leveled"] is False
    finally:
        xp_utils.DATA_DIR = orig_data_dir
