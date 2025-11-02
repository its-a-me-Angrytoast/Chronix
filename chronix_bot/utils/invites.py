"""Invite tracker utilities.

DB-first when a pool is available (uses chronix_bot.utils.db.get_pool()).
File-backed fallback `data/invites.json` for dev mode.

Features:
- Cache invite snapshots per guild (code -> uses + inviter)
- Record invite create/delete events
- Resolve inviter on member join by comparing cached invites
- Maintain per-user invite counts (successful invites, fake joins, leaves)
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from chronix_bot.utils.db import get_pool

INVITES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "invites.json")
INVITES_PATH = os.path.normpath(INVITES_PATH)

_file_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_file():
    d = os.path.dirname(INVITES_PATH)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(INVITES_PATH):
        async with _file_lock:
            with open(INVITES_PATH, "w", encoding="utf-8") as f:
                json.dump({"invites": [], "counts": {}}, f)


async def _read_all() -> Dict:
    await _ensure_file()
    async with _file_lock:
        with open(INVITES_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {"invites": [], "counts": {}}


async def _write_all(data: Dict):
    await _ensure_file()
    async with _file_lock:
        with open(INVITES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class InviteSnapshot:
    """Snapshot per guild of invites: maps code -> (uses, inviter_id).
    This is an in-memory cache only; persisted rows are stored in DB or file.
    """

    def __init__(self):
        self._snapshots: Dict[int, Dict[str, Dict]] = {}
        self._locks: Dict[int, asyncio.Lock] = {}

    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    async def set_snapshot(self, guild_id: int, invites: List[Dict]):
        async with self._lock_for(guild_id):
            self._snapshots[guild_id] = {inv["code"]: inv for inv in invites}

    async def get_snapshot(self, guild_id: int) -> Dict[str, Dict]:
        async with self._lock_for(guild_id):
            return dict(self._snapshots.get(guild_id, {}))


SNAP = InviteSnapshot()


async def record_invite_create(guild_id: int, code: str, inviter_id: int, uses: int = 0) -> None:
    pool = get_pool()
    ts = _now_iso()
    if pool is not None:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO invites (id, guild_id, code, inviter_id, uses, created_at, last_used) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $5) ON CONFLICT (code,guild_id) DO UPDATE SET inviter_id = EXCLUDED.inviter_id, uses = EXCLUDED.uses, last_used = EXCLUDED.last_used",
                int(guild_id), code, int(inviter_id), int(uses), ts,
            )
        return

    data = await _read_all()
    invites = data.get("invites", [])
    # replace if exists
    invites = [it for it in invites if not (it.get("code") == code and int(it.get("guild_id")) == int(guild_id))]
    invites.append({"guild_id": int(guild_id), "code": code, "inviter_id": int(inviter_id), "uses": int(uses), "created_at": ts, "last_used": ts})
    data["invites"] = invites
    await _write_all(data)


async def record_invite_delete(guild_id: int, code: str) -> None:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM invites WHERE guild_id = $1 AND code = $2", int(guild_id), code)
        return

    data = await _read_all()
    invites = data.get("invites", [])
    invites = [it for it in invites if not (it.get("code") == code and int(it.get("guild_id")) == int(guild_id))]
    data["invites"] = invites
    await _write_all(data)


async def increment_invite_use(guild_id: int, code: str, joined_user_id: Optional[int] = None, account_created_iso: Optional[str] = None) -> Optional[int]:
    """Increment uses for a code and return inviter_id if known.

    Optional parameters:
    - joined_user_id: ID of the member who joined (used for counting)
    - account_created_iso: ISO timestamp of the account creation (for fake-detection)

    When running in DB mode, updates are executed on a single connection and inside
    a transaction to avoid race conditions between incrementing invite uses and
    updating user counts.
    """
    def _is_fake_account_local(account_created_iso: Optional[str], threshold_seconds: int = 3 * 24 * 3600) -> bool:
        if not account_created_iso:
            return False
        try:
            from datetime import datetime
            import datetime as _dt

            created = datetime.fromisoformat(account_created_iso)
            age = (_dt.datetime.now(_dt.timezone.utc) - created).total_seconds()
            return age < threshold_seconds
        except Exception:
            return False

    pool = get_pool()
    if pool is not None:
        # keep this all on a single connection for safety
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "UPDATE invites SET uses = COALESCE(uses,0)+1, last_used = $1 WHERE guild_id = $2 AND code = $3 RETURNING inviter_id, uses",
                    _now_iso(), int(guild_id), code,
                )
                if row:
                    inviter = row["inviter_id"]
                    # determine fake or normal
                    if joined_user_id and _is_fake_account_local(account_created_iso):
                        await increment_fake_count_db(conn, int(guild_id), int(inviter), 1)
                    else:
                        await _increment_count_db(conn, int(guild_id), int(inviter), 1)
                    return inviter
        return None

    data = await _read_all()
    invites = data.get("invites", [])
    for it in invites:
        if int(it.get("guild_id")) == int(guild_id) and it.get("code") == code:
            it["uses"] = int(it.get("uses", 0)) + 1
            it["last_used"] = _now_iso()
            inviter = int(it.get("inviter_id"))
            data["invites"] = invites
            await _write_all(data)
            # increment counts (file-backed format supports dict values)
            counts = data.get("counts", {})
            key = f"{guild_id}:{inviter}"
            existing = counts.get(key, {})
            # support legacy integer format
            if isinstance(existing, int):
                existing = {"invites": int(existing), "fake": 0, "left": 0}

            # determine fake using same heuristic as DB path
            is_fake = False
            if joined_user_id and account_created_iso:
                try:
                    from datetime import datetime
                    import datetime as _dt

                    created = datetime.fromisoformat(account_created_iso)
                    age = (_dt.datetime.now(_dt.timezone.utc) - created).total_seconds()
                    is_fake = age < (3 * 24 * 3600)
                except Exception:
                    is_fake = False

            if is_fake:
                existing["fake"] = int(existing.get("fake", 0)) + 1
            else:
                existing["invites"] = int(existing.get("invites", 0)) + 1

            counts[key] = existing
            data["counts"] = counts
            await _write_all(data)
            return inviter
    return None


async def _increment_count_db(conn, guild_id: int, user_id: int, delta: int = 1):
    # increment the main invites_count column by delta
    await conn.execute(
        "INSERT INTO invite_counts (guild_id, user_id, invites_count) VALUES ($1,$2,$3) ON CONFLICT (guild_id,user_id) DO UPDATE SET invites_count = invite_counts.invites_count + $3",
        int(guild_id), int(user_id), int(delta),
    )


async def increment_fake_count_db(conn, guild_id: int, user_id: int, delta: int = 1):
    await conn.execute(
        "INSERT INTO invite_counts (guild_id, user_id, fake_count) VALUES ($1,$2,$3) ON CONFLICT (guild_id,user_id) DO UPDATE SET fake_count = invite_counts.fake_count + $3",
        int(guild_id), int(user_id), int(delta),
    )


async def increment_left_count_db(conn, guild_id: int, user_id: int, delta: int = 1):
    await conn.execute(
        "INSERT INTO invite_counts (guild_id, user_id, left_count) VALUES ($1,$2,$3) ON CONFLICT (guild_id,user_id) DO UPDATE SET left_count = invite_counts.left_count + $3",
        int(guild_id), int(user_id), int(delta),
    )


async def get_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[int, int]]:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, invites_count, fake_count, left_count FROM invite_counts WHERE guild_id = $1 ORDER BY invites_count DESC LIMIT $2",
                int(guild_id), limit,
            )
            return [(r["user_id"], r["invites_count"]) for r in rows]

    data = await _read_all()
    counts = data.get("counts", {})
    # keys like "guild:user"
    pairs = []
    for k, v in counts.items():
        g, u = k.split(":")
        if int(g) == int(guild_id):
            if isinstance(v, int):
                pairs.append((int(u), int(v)))
            elif isinstance(v, dict):
                pairs.append((int(u), int(v.get("invites", 0))))
            else:
                try:
                    pairs.append((int(u), int(v)))
                except Exception:
                    continue
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:limit]


async def get_user_counts(guild_id: int, user_id: int) -> Dict[str, int]:
    """Return structured counts for a user in a guild: {invites, fake, left}.

    Works in DB mode or file-backed mode.
    """
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT invites_count, fake_count, left_count FROM invite_counts WHERE guild_id = $1 AND user_id = $2",
                int(guild_id), int(user_id),
            )
            if not row:
                return {"invites": 0, "fake": 0, "left": 0}
            return {"invites": int(row.get("invites_count", 0)), "fake": int(row.get("fake_count", 0)), "left": int(row.get("left_count", 0))}

    data = await _read_all()
    counts = data.get("counts", {})
    key = f"{guild_id}:{user_id}"
    v = counts.get(key)
    if v is None:
        return {"invites": 0, "fake": 0, "left": 0}
    if isinstance(v, int):
        return {"invites": int(v), "fake": 0, "left": 0}
    if isinstance(v, dict):
        return {"invites": int(v.get("invites", 0)), "fake": int(v.get("fake", 0)), "left": int(v.get("left", 0))}
    try:
        return {"invites": int(v), "fake": 0, "left": 0}
    except Exception:
        return {"invites": 0, "fake": 0, "left": 0}


async def reset_guild_invites(guild_id: int) -> None:
    pool = get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM invites WHERE guild_id = $1", int(guild_id))
            await conn.execute("DELETE FROM invite_counts WHERE guild_id = $1", int(guild_id))
        return

    data = await _read_all()
    invites = [it for it in data.get("invites", []) if int(it.get("guild_id")) != int(guild_id)]
    counts = {k: v for k, v in data.get("counts", {}).items() if not k.startswith(f"{guild_id}:")}
    data["invites"] = invites
    data["counts"] = counts
    await _write_all(data)


__all__ = [
    "SNAP",
    "record_invite_create",
    "record_invite_delete",
    "increment_invite_use",
    "get_leaderboard",
    "reset_guild_invites",
]
