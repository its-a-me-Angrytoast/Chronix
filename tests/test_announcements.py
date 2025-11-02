import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from chronix_bot.utils import announcements as ann_utils


@pytest.mark.asyncio
async def test_create_and_get_and_delete(tmp_path):
    # ensure file path used is independent - but the util uses project data path
    # We'll exercise create/get/delete and basic fields
    payload = {"title": "Test", "description": "Hello"}
    now = datetime.now(timezone.utc)
    scheduled = (now + timedelta(seconds=1)).isoformat()
    rec = await ann_utils.create_announcement(1, 12345, 999, payload, scheduled_at=scheduled)
    assert rec.get("id")
    fetched = await ann_utils.get_announcement(rec["id"])
    assert fetched is not None
    assert fetched["payload"]["title"] == "Test"

    # delete
    ok = await ann_utils.delete_announcement(rec["id"])
    assert ok
    missing = await ann_utils.get_announcement(rec["id"])
    assert missing is None


@pytest.mark.asyncio
async def test_list_due_and_mark_posted():
    payload = {"title": "DueTest", "description": "Hi"}
    now = datetime.now(timezone.utc)
    scheduled = (now - timedelta(seconds=1)).isoformat()
    rec = await ann_utils.create_announcement(1, 12345, 999, payload, scheduled_at=scheduled)
    due = await ann_utils.list_due(now=now)
    ids = [d["id"] for d in due]
    assert rec["id"] in ids

    # mark posted disables by default
    ok = await ann_utils.mark_posted(rec["id"]) 
    assert ok
    fetched = await ann_utils.get_announcement(rec["id"])
    assert fetched is not None
    assert fetched.get("enabled") is False


@pytest.mark.asyncio
async def test_templates():
    name = "testtpl"
    content = {"title": "Tpl", "description": "desc"}
    created = await ann_utils.create_template(name, content)
    assert created["content"]["title"] == "Tpl"
    all_tpls = await ann_utils.list_templates()
    assert name in all_tpls
    got = await ann_utils.get_template(name)
    assert got is not None
    ok = await ann_utils.delete_template(name)
    assert ok
    missing = await ann_utils.get_template(name)
    assert missing is None
