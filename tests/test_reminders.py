import os
import time
import json
import pytest

from chronix_bot.utils import reminders


def _clear_file():
    f = reminders.REMINDERS_FILE
    if f.exists():
        f.unlink()


def test_add_and_remove_reminder():
    _clear_file()
    now = int(time.time())
    entry = reminders.add_reminder(12345, now + 5, "test reminder", guild_id=1)
    assert "id" in entry
    data = reminders.list_reminders()
    assert isinstance(data, dict)
    rems = data.get("reminders", [])
    assert any(r.get("id") == entry["id"] for r in rems)
    removed = reminders.remove_reminder(entry["id"])
    assert removed is True
    data2 = reminders.list_reminders()
    rems2 = data2.get("reminders", [])
    assert all(r.get("id") != entry["id"] for r in rems2)
