"""Announcement persistence and helpers.

DB-first when asyncpg is available and DATABASE_DSN/DATABASE_URL is configured.
File-backed fallback stores announcements in `data/announcements.json`.

Each announcement record (file-backed) schema:
{
    "id": "uuid",
    "guild_id": int,
    "channel_id": int,
    "author_id": int,
    "payload": {title, description, image, buttons, mentions},
    "scheduled_at": "iso8601 or null",
    "repeat": "cron-like string or null",
    "enabled": true,
    "created_at": "iso"
}
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from chronix_bot.utils.db import get_pool

try:
    from croniter import croniter
except Exception:
    croniter = None


ANNOUNCEMENTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "announcements.json")
ANNOUNCEMENTS_PATH = os.path.normpath(ANNOUNCEMENTS_PATH)

_file_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_uuid(u: Optional[str]) -> str:
    return u or str(uuid.uuid4())


async def _ensure_file():
    d = os.path.dirname(ANNOUNCEMENTS_PATH)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(ANNOUNCEMENTS_PATH):
        async with _file_lock:
            with open(ANNOUNCEMENTS_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)


async def _read_all() -> List[Dict[str, Any]]:
    await _ensure_file()
    async with _file_lock:
        with open(ANNOUNCEMENTS_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []


async def _write_all(items: List[Dict[str, Any]]):
    await _ensure_file()
    async with _file_lock:
        with open(ANNOUNCEMENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)


def _compute_next_from_repeat(repeat: Optional[str], base: Optional[datetime] = None) -> Optional[str]:
    """Return next scheduled ISO string based on repeat spec.

    Supports:
    - cron expressions (if `croniter` is installed)
    - `every Xm` / `every Xh` shorthand
    """
    if not repeat:
        return None
    now = base or _now_dt()
    repeat = repeat.strip()
    if croniter is not None and not repeat.startswith("every "):
        try:
            it = croniter(repeat, now)
            nxt = it.get_next(datetime)
            return nxt.astimezone(timezone.utc).isoformat()
        except Exception:
            # fall back to simple parsing
            pass

    if repeat.startswith("every "):
        spec = repeat.split(" ", 1)[1]
        if spec.endswith("m"):
            try:
                mins = int(spec[:-1])
                return (now + timedelta(minutes=mins)).astimezone(timezone.utc).isoformat()
            except Exception:
                return None
        if spec.endswith("h"):
            try:
                hrs = int(spec[:-1])
                return (now + timedelta(hours=hrs)).astimezone(timezone.utc).isoformat()
            except Exception:
                return None

    return None


async def create_announcement(guild_id: int, channel_id: int, author_id: int, payload: Dict[str, Any], scheduled_at: Optional[str] = None, repeat: Optional[str] = None) -> Dict[str, Any]:
    """Create and persist an announcement.

    Uses DB if a pool is available (Postgres), otherwise file-backed JSON.
    Returns the stored record.
    """
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO announcements (id, guild_id, channel_id, author_id, payload, scheduled_at, repeat, enabled, created_at, failure_count) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,0) RETURNING id, guild_id, channel_id, author_id, payload, scheduled_at, repeat, enabled, created_at, failure_count",
                str(uuid.uuid4()),
                int(guild_id),
                int(channel_id),
                int(author_id),
                json.dumps(payload),
                scheduled_at,
                repeat,
                True,
                _now_dt(),
            )
            if row is None:
                raise RuntimeError("Failed to insert announcement")
            return dict(row)

    # file-backed fallback
    record = {
        "id": str(uuid.uuid4()),
        "guild_id": int(guild_id),
        "channel_id": int(channel_id),
        "author_id": int(author_id),
        "payload": payload,
        "scheduled_at": scheduled_at,
        "repeat": repeat,
        "enabled": True,
        "created_at": _now_iso(),
        "failure_count": 0,
    }
    items = await _read_all()
    items.append(record)
    await _write_all(items)
    return record


async def get_announcement(ann_id: str) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, guild_id, channel_id, author_id, payload, scheduled_at, repeat, enabled, created_at, failure_count, last_failure FROM announcements WHERE id = $1", ann_id)
            if row is None:
                return None
            rec = dict(row)
            return rec

    items = await _read_all()
    for it in items:
        if it.get("id") == ann_id:
            return it
    return None


async def update_announcement(ann_id: str, **fields) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is not None:
        # build dynamic SET clause
        keys = []
        params = []
        idx = 1
        for k, v in fields.items():
            keys.append(f"{k} = ${idx}")
            # if updating payload, ensure JSON serialization handled by asyncpg
            if k == "payload":
                params.append(json.dumps(v))
            else:
                params.append(v)
            idx += 1
        if not keys:
            return await get_announcement(ann_id)
        sql = f"UPDATE announcements SET {', '.join(keys)} WHERE id = ${idx} RETURNING id, guild_id, channel_id, author_id, payload, scheduled_at, repeat, enabled, created_at, failure_count, last_failure"
        params.append(ann_id)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
            return dict(row) if row else None

    items = await _read_all()
    for i, it in enumerate(items):
        if it.get("id") == ann_id:
            it.update(fields)
            items[i] = it
            await _write_all(items)
            return it
    return None


async def delete_announcement(ann_id: str) -> bool:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("DELETE FROM announcements WHERE id = $1 RETURNING id", ann_id)
            return row is not None

    items = await _read_all()
    new = [it for it in items if it.get("id") != ann_id]
    if len(new) == len(items):
        return False
    await _write_all(new)
    return True


async def list_for_guild(guild_id: int) -> List[Dict[str, Any]]:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, guild_id, channel_id, author_id, payload, scheduled_at, repeat, enabled, created_at, failure_count, last_failure FROM announcements WHERE guild_id = $1 ORDER BY scheduled_at NULLS LAST", int(guild_id))
            return [dict(r) for r in rows]

    items = await _read_all()
    return [it for it in items if int(it.get("guild_id")) == int(guild_id)]


async def list_due(now: Optional[datetime] = None, limit: int = 50) -> List[Dict[str, Any]]:
    if now is None:
        now = _now_dt()
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, guild_id, channel_id, author_id, payload, scheduled_at, repeat, enabled, created_at, failure_count, last_failure FROM announcements WHERE enabled = true AND scheduled_at IS NOT NULL AND scheduled_at <= $1 ORDER BY scheduled_at ASC LIMIT $2", now, limit)
            return [dict(r) for r in rows]

    items = await _read_all()
    due = []
    for it in items:
        if not it.get("enabled", True):
            continue
        sa = it.get("scheduled_at")
        if not sa:
            continue
        try:
            dt = datetime.fromisoformat(sa)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if dt <= now:
            due.append(it)
            if len(due) >= limit:
                break
    return due


async def mark_posted(ann_id: str, next_scheduled_at: Optional[str] = None) -> bool:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            if next_scheduled_at:
                row = await conn.fetchrow("UPDATE announcements SET scheduled_at = $1, failure_count = 0, last_failure = NULL WHERE id = $2 RETURNING id", next_scheduled_at, ann_id)
            else:
                row = await conn.fetchrow("UPDATE announcements SET enabled = false WHERE id = $1 RETURNING id", ann_id)
            return row is not None

    items = await _read_all()
    for i, it in enumerate(items):
        if it.get("id") == ann_id:
            if next_scheduled_at:
                it["scheduled_at"] = next_scheduled_at
                it["failure_count"] = 0
                it["last_failure"] = None
            else:
                it["enabled"] = False
            items[i] = it
            await _write_all(items)
            return True
    return False


async def increment_failure(ann_id: str) -> None:
    """Increment failure_count and set last_failure timestamp for an announcement."""
    pool = get_pool()
    now = _now_dt()
    if pool is not None:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE announcements SET failure_count = COALESCE(failure_count,0) + 1, last_failure = $1 WHERE id = $2", now, ann_id)
        return

    items = await _read_all()
    for i, it in enumerate(items):
        if it.get("id") == ann_id:
            it["failure_count"] = int(it.get("failure_count", 0)) + 1
            it["last_failure"] = now.isoformat()
            items[i] = it
            await _write_all(items)
            return


# --- Template helpers (file-backed) ------------------------------------------------
TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "announcement_templates.json")
TEMPLATES_PATH = os.path.normpath(TEMPLATES_PATH)


async def _ensure_templates_file():
    d = os.path.dirname(TEMPLATES_PATH)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(TEMPLATES_PATH):
        async with _file_lock:
            with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)


async def create_template(name: str, content: Dict[str, Any]) -> Dict[str, Any]:
    await _ensure_templates_file()
    async with _file_lock:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
        data[name] = {"content": content, "created_at": _now_iso()}
        async with _file_lock:
            with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    return data[name]


async def list_templates() -> Dict[str, Any]:
    await _ensure_templates_file()
    async with _file_lock:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}


async def get_template(name: str) -> Optional[Dict[str, Any]]:
    data = await list_templates()
    return data.get(name)


async def delete_template(name: str) -> bool:
    data = await list_templates()
    if name not in data:
        return False
    data.pop(name)
    async with _file_lock:
        with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return True


__all__ = [
    "create_announcement",
    "update_announcement",
    "delete_announcement",
    "list_for_guild",
    "get_announcement",
    "list_due",
    "mark_posted",
    "increment_failure",
    "_compute_next_from_repeat",
    "create_template",
    "list_templates",
    "get_template",
    "delete_template",
]

