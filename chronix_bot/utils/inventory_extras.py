"""Additional inventory helpers: removal and transfer utilities.

These helpers use the file-backed inventory when no DB pool is available
and perform atomic DB operations when a pool exists.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from chronix_bot.utils import db as db_utils
from chronix_bot.utils import inventory


def remove_item(user_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    """Remove (and return) an item from a user's file-backed inventory.

    Returns the removed item dict or None if not found.
    """
    with inventory._lock:
        data = inventory._load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        items = bucket.setdefault("items", [])
        for i, it in enumerate(items):
            try:
                if int(it.get("item_id")) == int(item_id):
                    removed = items.pop(i)
                    bucket["items"] = items
                    data[str(user_id)] = bucket
                    inventory._save_all(data)
                    return removed
            except Exception:
                continue
    return None


async def async_remove_item(user_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    """Async remove an item. If a DB pool exists, perform a transactional removal.

    Falls back to file-backed remove_item when no pool is available.
    """
    pool = db_utils.get_pool()
    if pool is None:
        return remove_item(user_id, item_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, item_type, name, meta FROM user_items WHERE id = $1 AND user_id = $2 FOR UPDATE",
                int(item_id),
                int(user_id),
            )
            if row is None:
                return None
            await conn.execute("DELETE FROM user_items WHERE id = $1", int(item_id))
            try:
                meta = json.loads(row["meta"]) if row.get("meta") else {}
            except Exception:
                meta = {}
            return {"item_id": int(row["id"]), "name": row.get("name"), "meta": meta}


async def async_transfer_item(from_user: int, to_user: int, item_id: int) -> Optional[Dict[str, Any]]:
    """Transfer an item from one user to another.

    If a DB pool is available this is done atomically; otherwise the file-backed
    store is used. Returns the transferred item dict on success, or None.
    """
    pool = db_utils.get_pool()
    if pool is None:
        # file-backed transfer: remove from source and append to target preserving the dict
        with inventory._lock:
            data = inventory._load_all()
            src = data.setdefault(str(from_user), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            tgt = data.setdefault(str(to_user), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            items = src.setdefault("items", [])
            for i, it in enumerate(items):
                try:
                    if int(it.get("item_id")) == int(item_id):
                        transferred = items.pop(i)
                        # ensure item_id uniqueness for target: assign a new timestamp id
                        new_id = int(time.time() * 1000)
                        transferred["item_id"] = new_id
                        tgt.setdefault("items", []).append(transferred)
                        data[str(from_user)] = src
                        data[str(to_user)] = tgt
                        inventory._save_all(data)
                        return transferred
                except Exception:
                    continue
        return None

    # DB-backed transfer: do an atomic update of the owner_id
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, item_type, name, meta, user_id FROM user_items WHERE id = $1 FOR UPDATE",
                int(item_id),
            )
            if row is None:
                return None
            if int(row.get("user_id")) != int(from_user):
                return None
            await conn.execute("UPDATE user_items SET user_id = $1 WHERE id = $2", int(to_user), int(item_id))
            try:
                meta = json.loads(row["meta"]) if row.get("meta") else {}
            except Exception:
                meta = {}
            return {"item_id": int(row["id"]), "name": row.get("name"), "meta": meta}
