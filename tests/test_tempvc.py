import asyncio
import os
import json

import pytest

from chronix_bot.utils import tempvc


@pytest.mark.asyncio
async def test_generate_name():
    n = tempvc.generate_name("{user}-vc", "Alice")
    assert "alice" in n


@pytest.mark.asyncio
async def test_file_persistence(tmp_path, monkeypatch):
    temp = tmp_path / "tempvc.json"
    temp.write_text(json.dumps({"configs": {}, "channels": {}}))
    monkeypatch.setattr(tempvc, "PATH", str(temp))
    await tempvc.set_config(1, {"name_pattern": "{user}-party", "auto_delete_seconds": 1, "max_per_user": 1})
    cfg = await tempvc.get_config(1)
    assert cfg["name_pattern"] == "{user}-party"
    await tempvc.create_channel_record(1, 1234, 42, channel_type="voice")
    ll = await tempvc.list_guild_channels(1)
    assert any(r["owner_id"] == 42 for r in ll)
    # cleanup_expired should eventually include the record after threshold
    expired = await tempvc.cleanup_expired(threshold_seconds=0)
    assert 1234 in expired


def test_generate_name_sanitization():
    n = tempvc.generate_name("{user} *VIP*", "A!lice")
    # sanitized to lowercase alnum/dash/underscore
    assert "!" not in n and "*" not in n