"""Temporary channel utilities (file-backed with DB-ready design).

Responsibilities:
- per-guild config (category, name pattern, auto-delete seconds, max_per_user, channel_type)
- persistent records of active temp channels (channel_id -> owner_id, created_at, last_active)
- helpers to create names from patterns
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

_LOCK = asyncio.Lock()
PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "tempvc.json"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_file():
    d = os.path.dirname(PATH)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(PATH):
        async with _LOCK:
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump({"configs": {}, "channels": {}}, f)


async def _read_all() -> Dict[str, Any]:
    await _ensure_file()
    async with _LOCK:
        with open(PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {"configs": {}, "channels": {}}


async def _write_all(data: Dict[str, Any]):
    await _ensure_file()
    async with _LOCK:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def get_config(guild_id: int) -> Dict[str, Any]:
    data = await _read_all()
    cfg = data.get("configs", {}).get(str(guild_id), {})
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "category_id": cfg.get("category_id"),
        "name_pattern": cfg.get("name_pattern", "{user}-vc"),
        "auto_delete_seconds": int(cfg.get("auto_delete_seconds", 300)),
        "max_per_user": int(cfg.get("max_per_user", 2)),
        "text_channels": bool(cfg.get("text_channels", False)),
        "log_channel_id": cfg.get("log_channel_id"),
    }


async def set_config(guild_id: int, cfg: Dict[str, Any]):
    data = await _read_all()
    if "configs" not in data:
        data["configs"] = {}
    data["configs"][str(guild_id)] = cfg
    await _write_all(data)


async def create_channel_record(guild_id: int, channel_id: int, owner_id: int, channel_type: str = "voice") -> None:
    data = await _read_all()
    ch = data.setdefault("channels", {})
    ch[str(channel_id)] = {
        "guild_id": int(guild_id),
        "owner_id": int(owner_id),
        "created_at": _now_iso(),
        "last_active": _now_iso(),
        "type": channel_type,
    }
    data["channels"] = ch
    # record a creation event for rate-limiting / auditing
    events = data.setdefault("creation_events", {})
    gkey = str(guild_id)
    events.setdefault(gkey, [])
    events[gkey].append({"ts": _now_iso(), "owner_id": int(owner_id), "channel_id": int(channel_id)})
    data["creation_events"] = events
    await _write_all(data)


async def update_last_active(channel_id: int) -> None:
    data = await _read_all()
    ch = data.get("channels", {})
    key = str(channel_id)
    if key in ch:
        ch[key]["last_active"] = _now_iso()
        data["channels"] = ch
        await _write_all(data)


async def delete_channel_record(channel_id: int) -> None:
    data = await _read_all()
    ch = data.get("channels", {})
    key = str(channel_id)
    if key in ch:
        del ch[key]
        data["channels"] = ch
        await _write_all(data)


async def list_guild_channels(guild_id: int) -> List[Dict[str, Any]]:
    data = await _read_all()
    out = []
    for k, v in data.get("channels", {}).items():
        if int(v.get("guild_id")) == int(guild_id):
            rec = dict(v)
            rec["channel_id"] = int(k)
            out.append(rec)
    return out


async def get_all_channel_ids() -> List[int]:
    """Return all tracked channel ids as integers."""
    data = await _read_all()
    return [int(k) for k in data.get("channels", {}).keys()]


async def get_channel_record(channel_id: int) -> Optional[Dict[str, Any]]:
    data = await _read_all()
    rec = data.get("channels", {}).get(str(channel_id))
    return rec


async def cleanup_expired(threshold_seconds: Optional[int] = None) -> List[int]:
    """Return list of channel IDs that are expired (last_active older than threshold).

    If threshold_seconds is None, use per-guild config for each channel. This helper
    will check all channels and return IDs that should be cleaned up (but not delete them).
    """
    now = datetime.now(timezone.utc)
    data = await _read_all()
    expired = []
    channels = data.get("channels", {})
    configs = data.get("configs", {})
    for cid, rec in channels.items():
        gid = str(rec.get("guild_id"))
        cfg = configs.get(gid, {})
        auto = int(cfg.get("auto_delete_seconds", 300)) if threshold_seconds is None else int(threshold_seconds)
        last = rec.get("last_active")
        try:
            last_dt = datetime.fromisoformat(last)
        except Exception:
            last_dt = now
        age = (now - last_dt).total_seconds()
        if age >= auto:
            expired.append(int(cid))
    return expired


async def record_creation_event(guild_id: int, owner_id: int, channel_id: int) -> None:
    """Append a creation event used by rate-limit checks.

    Stored under `creation_events` keyed by guild id. This is intentionally
    simple and survives restarts to help moderate burst creation across bot
    restarts.
    """
    data = await _read_all()
    events = data.setdefault("creation_events", {})
    gkey = str(guild_id)
    events.setdefault(gkey, [])
    events[gkey].append({"ts": _now_iso(), "owner_id": int(owner_id), "channel_id": int(channel_id)})
    data["creation_events"] = events
    await _write_all(data)


async def _trim_creation_events(guild_id: int, window_seconds: int = 60) -> None:
    """Trim creation events older than window_seconds for the guild.

    This keeps the underlying file small.
    """
    data = await _read_all()
    events = data.setdefault("creation_events", {})
    gkey = str(guild_id)
    now = datetime.now(timezone.utc)
    lst = events.get(gkey, [])
    if not lst:
        return
    out = []
    for ent in lst:
        try:
            ts = datetime.fromisoformat(ent.get("ts"))
        except Exception:
            continue
        if (now - ts).total_seconds() <= window_seconds:
            out.append(ent)
    events[gkey] = out
    data["creation_events"] = events
    await _write_all(data)


async def can_create_now(guild_id: int, owner_id: int, *, per_guild_limit: int = 10, per_user_limit: int = 3, window_seconds: int = 60) -> bool:
    """Return True if creating a new temp channel is allowed under rate limits.

    - per_guild_limit: max channels created in window_seconds across the guild
    - per_user_limit: max channels created by the user in window_seconds
    """
    await _trim_creation_events(guild_id, window_seconds=window_seconds)
    data = await _read_all()
    events = data.get("creation_events", {})
    gkey = str(guild_id)
    lst = events.get(gkey, [])
    now = datetime.now(timezone.utc)
    guild_count = 0
    user_count = 0
    for ent in lst:
        try:
            ts = datetime.fromisoformat(ent.get("ts"))
        except Exception:
            continue
        if (now - ts).total_seconds() <= window_seconds:
            guild_count += 1
            if int(ent.get("owner_id")) == int(owner_id):
                user_count += 1

    if guild_count >= per_guild_limit or user_count >= per_user_limit:
        return False
    return True


def generate_name(pattern: str, username: str, counter: Optional[int] = None) -> str:
    """Generate a channel name from pattern. Supported tokens: {user}, {count}.

    Keeps name safe (lowercase, spaces -> -).
    """
    s = pattern.replace("{user}", username)
    if counter is not None:
        s = s.replace("{count}", str(counter))
    s = s.strip().lower().replace(" ", "-")
    # sanitize: keep alphanum, dash, underscore
    import re

    s = re.sub(r"[^a-z0-9-_]", "", s)
    return s[:90]


__all__ = [
    "get_config",
    "set_config",
    "create_channel_record",
    "update_last_active",
    "delete_channel_record",
    "list_guild_channels",
    "cleanup_expired",
    "generate_name",
]
