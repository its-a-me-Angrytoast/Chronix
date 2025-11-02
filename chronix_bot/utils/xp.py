"""XP utilities: file-backed async helpers for XP and level calculations.

This module prefers a DB-backed implementation when available; for dev it
stores XP in `data/xp.json` and per-guild settings in `data/guild_xp_settings.json`.

Functions are async and use asyncio.to_thread for file I/O to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import time
from typing import Dict, Tuple, Optional, List
from pathlib import Path

try:
    import asyncpg
except Exception:  # pragma: no cover - optional dependency
    asyncpg = None

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
XP_FILE = DATA_DIR / "xp.json"
GUILD_SETTINGS_FILE = DATA_DIR / "guild_xp_settings.json"

# simple in-memory locks to avoid concurrent file writes
_locks: Dict[str, asyncio.Lock] = {}

# DB pool (lazily created if DATABASE_DSN is present)
_db_pool = None


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not XP_FILE.exists():
        XP_FILE.write_text("{}")
    if not GUILD_SETTINGS_FILE.exists():
        GUILD_SETTINGS_FILE.write_text("{}")


def _get_lock(name: str) -> asyncio.Lock:
    if name not in _locks:
        _locks[name] = asyncio.Lock()
    return _locks[name]


def xp_for_level(level: int, base: int = 100) -> int:
    """Compute XP required to reach given level (total XP threshold).

    Formula: xp = base * level^2
    """
    if level <= 0:
        return 0
    return base * (level ** 2)


def level_from_xp(xp: int, base: int = 100) -> int:
    if xp <= 0:
        return 0
    return int(math.floor(math.sqrt(xp / base)))


async def _read_json(path: Path) -> dict:
    _ensure_data_dir()
    content = await asyncio.to_thread(path.read_text)
    try:
        return json.loads(content or "{}")
    except Exception:
        return {}


async def _write_json(path: Path, data: dict) -> None:
    _ensure_data_dir()
    text = json.dumps(data, indent=2, ensure_ascii=False)
    await asyncio.to_thread(path.write_text, text)


async def _get_db_pool():
    global _db_pool
    if _db_pool is not None:
        return _db_pool
    dsn = os.getenv("DATABASE_DSN") or os.getenv("DATABASE_URL") or os.getenv("DATABASE_DSN")
    if not dsn or asyncpg is None:
        return None
    _db_pool = await asyncpg.create_pool(dsn, min_size=int(os.getenv("DB_POOL_MIN", "1")), max_size=int(os.getenv("DB_POOL_MAX", "10")))
    return _db_pool


async def get_guild_settings(guild_id: int) -> dict:
    """Return per-guild XP settings. Uses DB when available, otherwise file-backed JSON."""
    pool = await _get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT settings FROM guild_xp_settings WHERE guild_id=$1", int(guild_id))
            if row and row.get("settings"):
                return row["settings"]
            return {}

    lock = _get_lock("settings")
    async with lock:
        data = await _read_json(GUILD_SETTINGS_FILE)
        return data.get(str(guild_id), {})


async def set_guild_settings(guild_id: int, settings: dict) -> None:
    pool = await _get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO guild_xp_settings (guild_id, settings) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET settings = EXCLUDED.settings",
                int(guild_id), settings,
            )
            return

    lock = _get_lock("settings")
    async with lock:
        data = await _read_json(GUILD_SETTINGS_FILE)
        data[str(guild_id)] = settings
        await _write_json(GUILD_SETTINGS_FILE, data)


async def add_xp(guild_id: int, user_id: int, amount: int, base: int = 100, multiplier: float = 1.0) -> dict:
    """Add XP using DB when available; otherwise fall back to file-backed atomic writes.

    Returns a dict with old_xp, new_xp, old_level, new_level, leveled, gained
    """
    pool = await _get_db_pool()
    add_amount = int(math.floor(amount * multiplier))
    if pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT xp FROM users_xp WHERE guild_id=$1 AND user_id=$2 FOR UPDATE", int(guild_id), int(user_id))
                old_xp = int(row["xp"]) if row else 0
                new_xp = old_xp + add_amount
                if row:
                    await conn.execute("UPDATE users_xp SET xp=$1 WHERE guild_id=$2 AND user_id=$3", new_xp, int(guild_id), int(user_id))
                else:
                    await conn.execute("INSERT INTO users_xp (guild_id, user_id, xp) VALUES ($1,$2,$3)", int(guild_id), int(user_id), new_xp)
        old_level = level_from_xp(old_xp, base)
        new_level = level_from_xp(new_xp, base)
        return {"old_xp": old_xp, "new_xp": new_xp, "old_level": old_level, "new_level": new_level, "leveled": new_level > old_level, "gained": add_amount}

    # file-backed path
    _ensure_data_dir()
    lock = _get_lock("xp")
    async with lock:
        all_xp = await _read_json(XP_FILE)
        guild = all_xp.setdefault(str(guild_id), {})
        old_xp = int(guild.get(str(user_id), 0))
        new_xp = old_xp + add_amount
        guild[str(user_id)] = new_xp
        await _write_json(XP_FILE, all_xp)

    old_level = level_from_xp(old_xp, base)
    new_level = level_from_xp(new_xp, base)
    return {"old_xp": old_xp, "new_xp": new_xp, "old_level": old_level, "new_level": new_level, "leveled": new_level > old_level, "gained": add_amount}


async def get_xp(guild_id: int, user_id: int) -> int:
    pool = await _get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT xp FROM users_xp WHERE guild_id=$1 AND user_id=$2", int(guild_id), int(user_id))
            return int(row["xp"]) if row else 0

    _ensure_data_dir()
    data = await _read_json(XP_FILE)
    return int(data.get(str(guild_id), {}).get(str(user_id), 0))


async def get_top(guild_id: int, limit: int = 10) -> List[Tuple[int, int]]:
    pool = await _get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, xp FROM users_xp WHERE guild_id=$1 ORDER BY xp DESC LIMIT $2", int(guild_id), int(limit))
            return [(int(r["user_id"]), int(r["xp"])) for r in rows]

    _ensure_data_dir()
    data = await _read_json(XP_FILE)
    guild = data.get(str(guild_id), {})
    items = [(int(uid), int(xp)) for uid, xp in guild.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:limit]


async def get_global_top(limit: int = 10) -> List[Tuple[int, int]]:
    """Return global top users by XP across all guilds.

    Uses DB when available, otherwise aggregates file-backed data.
    """
    pool = await _get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, SUM(xp) AS total FROM users_xp GROUP BY user_id ORDER BY total DESC LIMIT $1", int(limit))
            return [(int(r["user_id"]), int(r["total"])) for r in rows]

    data = await _read_json(XP_FILE)
    totals: Dict[int, int] = {}
    for guild_data in data.values():
        for uid, xp in guild_data.items():
            totals[int(uid)] = totals.get(int(uid), 0) + int(xp)
    items = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    return items[:limit]


async def reset_guild_xp(guild_id: int) -> None:
    pool = await _get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM users_xp WHERE guild_id=$1", int(guild_id))
            return

    lock = _get_lock("xp")
    async with lock:
        data = await _read_json(XP_FILE)
        data[str(guild_id)] = {}
        await _write_json(XP_FILE, data)


async def backup_xp(dest: Optional[str] = None) -> str:
    _ensure_data_dir()
    ts = int(time.time())
    dest_name = dest or f"xp_backup_{ts}.json"
    dest_path = DATA_DIR / dest_name
    lock = _get_lock("xp")
    async with lock:
        content = await asyncio.to_thread(XP_FILE.read_text)
        await asyncio.to_thread(dest_path.write_text, content)
    return str(dest_path)
