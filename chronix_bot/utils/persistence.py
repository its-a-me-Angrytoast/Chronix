"""Scaffold for DB-backed persistence to replace file-backed reminders and inventory.

This module provides placeholder async functions and an adapter interface. The
current project uses file-backed stores during early phases. When ready, implement
these functions to use `chronix_bot.utils.db` asyncpg pool and the models in
`chronix_bot.utils.models`.

Usage:
- Import `Persistence` and call `Persistence.enable_db(pool)` to switch to DB mode.
- Current functions will raise NotImplementedError when the DB backend is enabled.
"""
from __future__ import annotations

from typing import Optional, Dict, Any
import time

_db_enabled = False
_db_pool = None


def enable_db(pool) -> None:
    """Enable DB-backed persistence and provide an asyncpg pool or connection.

    For now this is a toggle; the actual DB methods are TODO and should be
    implemented when migrations and schema are available.
    """
    global _db_enabled, _db_pool
    _db_enabled = True
    _db_pool = pool


def is_db_enabled() -> bool:
    return _db_enabled


# Reminder interface (mirror of chronix_bot.utils.reminders)
async def add_reminder_db(user_id: int, when_ts: int, message: str, guild_id: Optional[int] = None) -> Dict[str, Any]:
    """Add reminder to DB-backed store. TODO: implement.

    Raises NotImplementedError until DB persistence is implemented.
    """
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed persistence for reminders is not implemented yet")


async def remove_reminder_db(reminder_id: str) -> bool:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed persistence for reminders is not implemented yet")


async def list_reminders_db() -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed persistence for reminders is not implemented yet")


# Inventory interface (mirror of chronix_bot.utils.inventory)
async def add_gem_db(user_id: int, gem_type: str, power: int = 1) -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed inventory not implemented yet")

async def merge_gems_db(user_id: int, gem_type: str, count: int = 2) -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed inventory not implemented yet")


async def add_pet_db(user_id: int, species: str) -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed inventory not implemented yet")


# Simple file-backed guild settings (used until DB persistence is implemented)
from pathlib import Path
import json

DATA_DIR = Path.cwd() / "data"
GUILD_SETTINGS_FILE = DATA_DIR / "guild_settings.json"


def _load_gsettings() -> Dict[str, Any]:
    if not GUILD_SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(GUILD_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_gsettings(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GUILD_SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_guild_setting(guild_id: int, key: str, default=None):
    data = _load_gsettings()
    g = data.get(str(guild_id), {})
    return g.get(key, default)


def set_guild_setting(guild_id: int, key: str, value) -> None:
    data = _load_gsettings()
    g = data.setdefault(str(guild_id), {})
    g[key] = value
    data[str(guild_id)] = g
    _save_gsettings(data)


# ----- simple moderation case storage (file-backed until DB available)
CASES_FILE = DATA_DIR / "mod_cases.json"


def _load_cases() -> dict:
    if not CASES_FILE.exists():
        return {"next_id": 1, "cases": {}}
    try:
        return json.loads(CASES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"next_id": 1, "cases": {}}


def _save_cases(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CASES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_case(guild_id: int, moderator_id: int, target_id: int, action: str, reason: str) -> dict:
    data = _load_cases()
    nid = int(data.get("next_id", 1))
    case = {
        "id": nid,
        "guild_id": int(guild_id),
        "moderator_id": int(moderator_id),
        "target_id": int(target_id),
        "action": action,
        "reason": reason,
        "created_at": int(time.time()),
    }
    data.setdefault("cases", {})[str(nid)] = case
    data["next_id"] = nid + 1
    _save_cases(data)
    return case


def get_case(case_id: int) -> dict:
    data = _load_cases()
    return data.get("cases", {}).get(str(case_id))


def list_cases(guild_id: Optional[int] = None, limit: int = 25) -> list:
    data = _load_cases()
    cases = list(data.get("cases", {}).values())
    if guild_id is not None:
        cases = [c for c in cases if c.get("guild_id") == int(guild_id)]
    cases.sort(key=lambda c: c.get("created_at", 0), reverse=True)
    return cases[:limit]


# ----- warns storage (file-backed)
WARNS_FILE = DATA_DIR / "warns.json"


def _load_warns() -> dict:
    if not WARNS_FILE.exists():
        return {}
    try:
        return json.loads(WARNS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_warns(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WARNS_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def add_warn(guild_id: int, user_id: int, moderator_id: int, reason: str) -> dict:
    d = _load_warns()
    g = d.setdefault(str(guild_id), {})
    u = g.setdefault(str(user_id), [])
    entry = {"moderator_id": int(moderator_id), "reason": reason, "ts": int(time.time())}
    u.append(entry)
    g[str(user_id)] = u
    d[str(guild_id)] = g
    _save_warns(d)
    return entry


def get_warn_count(guild_id: int, user_id: int) -> int:
    d = _load_warns()
    return len(d.get(str(guild_id), {}).get(str(user_id), []))


def clear_warns(guild_id: int, user_id: int) -> None:
    d = _load_warns()
    g = d.get(str(guild_id), {})
    if str(user_id) in g:
        del g[str(user_id)]
    d[str(guild_id)] = g
    _save_warns(d)


# ----- appeals storage (file-backed)
APPEALS_FILE = DATA_DIR / "appeals.json"


def _load_appeals() -> dict:
    if not APPEALS_FILE.exists():
        return {"next_id": 1, "appeals": {}}
    try:
        return json.loads(APPEALS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"next_id": 1, "appeals": {}}


def _save_appeals(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPEALS_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def add_appeal(guild_id: int, user_id: int, content: str) -> dict:
    d = _load_appeals()
    nid = int(d.get("next_id", 1))
    appeal = {"id": nid, "guild_id": int(guild_id), "user_id": int(user_id), "content": content, "created_at": int(time.time())}
    d.setdefault("appeals", {})[str(nid)] = appeal
    d["next_id"] = nid + 1
    _save_appeals(d)
    return appeal


def list_appeals(guild_id: Optional[int] = None, limit: int = 25) -> list:
    d = _load_appeals()
    apps = list(d.get("appeals", {}).values())
    if guild_id is not None:
        apps = [a for a in apps if a.get("guild_id") == int(guild_id)]
    apps.sort(key=lambda a: a.get("created_at", 0), reverse=True)
    return apps[:limit]


# ----- moderation templates (file-backed until DB available)
TEMPLATES_FILE = DATA_DIR / "mod_templates.json"


def _load_templates() -> dict:
    if not TEMPLATES_FILE.exists():
        return {}
    try:
        return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_templates(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def add_mod_template(guild_id: int, name: str, content: str) -> dict:
    d = _load_templates()
    g = d.setdefault(str(guild_id), {})
    g[name] = {"name": name, "content": content}
    d[str(guild_id)] = g
    _save_templates(d)
    return g[name]


def list_mod_templates(guild_id: int) -> list:
    d = _load_templates()
    return list(d.get(str(guild_id), {}).values())


def remove_mod_template(guild_id: int, name: str) -> bool:
    d = _load_templates()
    g = d.get(str(guild_id), {})
    if name in g:
        del g[name]
        d[str(guild_id)] = g
        _save_templates(d)
        return True
    return False

