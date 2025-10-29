"""Simple reminders persistence and scheduler for Phase 6.

Stores reminders in `data/reminders.json` and schedules background tasks to
deliver reminders via DM. This is intentionally lightweight for development.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict, Any, List

DATA_DIR = Path.cwd() / "data"
REMINDERS_FILE = DATA_DIR / "reminders.json"
_lock = threading.Lock()


def _load() -> Dict[str, Any]:
    if not REMINDERS_FILE.exists():
        return {}
    try:
        return json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REMINDERS_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def list_reminders() -> Dict[str, Any]:
    return _load()


def add_reminder(user_id: int, when_ts: int, message: str, guild_id: int | None = None) -> Dict[str, Any]:
    with _lock:
        d = _load()
        rid = str(int(time.time() * 1000))
        entry = {"id": rid, "user_id": int(user_id), "when": int(when_ts), "message": message, "guild_id": int(guild_id) if guild_id else None}
        d.setdefault("reminders", []).append(entry)
        _save(d)
        return entry


def remove_reminder(reminder_id: str) -> bool:
    with _lock:
        d = _load()
        rems = d.get("reminders", [])
        new = [r for r in rems if r.get("id") != reminder_id]
        if len(new) == len(rems):
            return False
        d["reminders"] = new
        _save(d)
        return True
