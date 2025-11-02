"""Per-guild invite configuration (file-backed with DB-ready placeholders).

This module stores simple per-guild configs for the invite tracker:
- log_channel_id: optional channel to post invite logs
- enable_rewards: bool
- milestones: list of ints (when to fire invite_milestone)
- fake_threshold_seconds: account age threshold to consider a join fake

The implementation is file-backed for development and can be extended to use
the DB pool if desired.
"""
from __future__ import annotations

import json
import os
import asyncio
from typing import Dict, Any, Optional

_LOCK = asyncio.Lock()
PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "invite_configs.json")
PATH = os.path.normpath(PATH)


async def _ensure_file():
    d = os.path.dirname(PATH)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(PATH):
        async with _LOCK:
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)


async def _read_all() -> Dict[str, Any]:
    await _ensure_file()
    async with _LOCK:
        with open(PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}


async def _write_all(data: Dict[str, Any]):
    await _ensure_file()
    async with _LOCK:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def get_config(guild_id: int) -> Dict[str, Any]:
    data = await _read_all()
    key = str(guild_id)
    cfg = data.get(key, {})
    # defaults
    return {
        "log_channel_id": cfg.get("log_channel_id"),
        "enable_rewards": bool(cfg.get("enable_rewards", True)),
        "milestones": cfg.get("milestones", [5, 10, 25, 50]),
        "fake_threshold_seconds": int(cfg.get("fake_threshold_seconds", 3 * 24 * 3600)),
    }


async def set_config(guild_id: int, cfg: Dict[str, Any]):
    data = await _read_all()
    data[str(guild_id)] = cfg
    await _write_all(data)


async def set_log_channel(guild_id: int, channel_id: Optional[int]):
    data = await _read_all()
    key = str(guild_id)
    cur = data.get(key, {})
    cur["log_channel_id"] = int(channel_id) if channel_id is not None else None
    data[key] = cur
    await _write_all(data)


__all__ = [
    "get_config",
    "set_config",
    "set_log_channel",
]
