"""Simple inventory persistence for Phase 4.

Provides a lightweight file-backed inventory store with an in-memory fallback.
Stores per-user gems and pets under `data/inventories.json` for development.

APIs:
- add_gem(user_id, gem_type, power) -> gem dict
- list_gems(user_id) -> list[dict]
- merge_gems(user_id, gem_type, count=2) -> dict (new gem) or raises
- add_pet(user_id, species) -> pet dict
- list_pets(user_id) -> list[dict]
- feed_pet(user_id, pet_id) -> pet dict (level up)
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Dict, Any, List, Optional

DATA_DIR = Path.cwd() / "data"
INVENTORY_FILE = DATA_DIR / "inventories.json"
_lock = threading.Lock()


def _load_all() -> Dict[str, Any]:
    if not INVENTORY_FILE.exists():
        return {}
    try:
        return json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INVENTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _user_bucket(user_id: int) -> Dict[str, Any]:
    """Inventory utilities with file-backed fallback and DB-backed async APIs.

    This module exposes two orthogonal APIs:
    - synchronous file-backed helpers (existing usage in code): add_gem, add_pet, list_pets, etc.
    - asynchronous DB-backed helpers (async_*) which use `chronix_bot.utils.db` when a pool is present.

    Design: most existing code calls the sync helpers from async contexts; for new DB-backed flows we call the async_* helpers when a DB pool is initialized.
    """
    from __future__ import annotations

    import json
    from pathlib import Path
    import threading
    import time
    from typing import Dict, Any, List, Optional

    from chronix_bot.utils import db as db_utils

    DATA_DIR = Path.cwd() / "data"
    INVENTORY_FILE = DATA_DIR / "inventories.json"
    _lock = threading.Lock()


    def _load_all() -> Dict[str, Any]:
        if not INVENTORY_FILE.exists():
            return {}
        try:
            return json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}


    def _save_all(data: Dict[str, Any]) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        INVENTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


    def _user_bucket(user_id: int) -> Dict[str, Any]:
        data = _load_all()
        return data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})


    # ------------------
    # Synchronous, file-backed helpers (backwards compatible)
    # ------------------


    def add_gem(user_id: int, gem_type: str, power: int = 1) -> Dict[str, Any]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            gem_id = int(time.time() * 1000)
            gem = {"gem_id": gem_id, "gem_type": gem_type, "power": int(power)}
            bucket.setdefault("gems", []).append(gem)
            _save_all(data)
            return gem


    def list_gems(user_id: int) -> List[Dict[str, Any]]:
        data = _load_all()
        bucket = data.get(str(user_id), {})
        return bucket.get("gems", [])


    def merge_gems(user_id: int, gem_type: str, count: int = 2) -> Dict[str, Any]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            gems = [g for g in bucket.get("gems", []) if g.get("gem_type") == gem_type]
            if len(gems) < count:
                raise ValueError("Not enough gems to merge")
            gems_sorted = sorted(gems, key=lambda x: x.get("power", 0))
            to_consume = gems_sorted[:count]
            remaining = [g for g in bucket.get("gems", []) if g not in to_consume]
            max_power = max(g.get("power", 0) for g in to_consume)
            new_power = max_power + 1
            new_gem = {"gem_id": int(time.time() * 1000), "gem_type": gem_type, "power": new_power}
            remaining.append(new_gem)
            bucket["gems"] = remaining
            data[str(user_id)] = bucket
            _save_all(data)
            return new_gem


    def add_pet(user_id: int, species: str) -> Dict[str, Any]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            pet_id = int(time.time() * 1000)
            pet = {"pet_id": pet_id, "species": species, "level": 1, "xp": 0}
            bucket.setdefault("pets", []).append(pet)
            _save_all(data)
            return pet


    def list_pets(user_id: int) -> List[Dict[str, Any]]:
        data = _load_all()
        bucket = data.get(str(user_id), {})
        return bucket.get("pets", [])


    def feed_pet(user_id: int, pet_id: int, food_xp: int = 10) -> Dict[str, Any]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            pets = bucket.setdefault("pets", [])
            for p in pets:
                if int(p.get("pet_id")) == int(pet_id):
                    p["xp"] = p.get("xp", 0) + int(food_xp)
                    # level up for each 100 xp
                    while p["xp"] >= 100:
                        p["xp"] -= 100
                        p["level"] = p.get("level", 1) + 1
                    _save_all(data)
                    return p
            raise ValueError("Pet not found")


    def add_item(user_id: int, name: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            item_id = int(time.time() * 1000)
            item = {"item_id": item_id, "name": name, "meta": meta or {}}
            bucket.setdefault("items", []).append(item)
            _save_all(data)
            return item


    def list_items(user_id: int) -> List[Dict[str, Any]]:
        data = _load_all()
        bucket = data.get(str(user_id), {})
        return bucket.get("items", [])


    def add_unopened_crate(user_id: int, crate_type: str) -> Dict[str, Any]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            crate_id = int(time.time() * 1000)
            crate = {"crate_id": crate_id, "crate_type": crate_type}
            bucket.setdefault("unopened_crates", []).append(crate)
            _save_all(data)
            return crate


    def list_unopened_crates(user_id: int) -> List[Dict[str, Any]]:
        data = _load_all()
        bucket = data.get(str(user_id), {})
        return bucket.get("unopened_crates", [])


    def consume_unopened_crate(user_id: int, crate_type: str) -> Optional[Dict[str, Any]]:
        with _lock:
            data = _load_all()
            bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
            crates = bucket.setdefault("unopened_crates", [])
            for i, c in enumerate(crates):
                if c.get("crate_type") == crate_type:
                    removed = crates.pop(i)
                    bucket["unopened_crates"] = crates
                    data[str(user_id)] = bucket
                    _save_all(data)
                    return removed
        return None


    # ------------------
    # Async DB-backed helpers
    # ------------------


    async def async_add_item(user_id: int, name: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pool = db_utils.get_pool()
        if pool is None:
            # fallback to file-backed
            return add_item(user_id, name, meta=meta)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO user_items (user_id, item_type, name, meta, created_at) VALUES ($1,$2,$3,$4,now()) RETURNING id",
                user_id,
                str(meta.get("type") if meta and "type" in meta else "misc"),
                name,
                json.dumps(meta or {}),
            )
            return {"item_id": row["id"], "name": name, "meta": meta or {}}


    async def async_add_unopened_crate(user_id: int, crate_type: str, gifted_from: Optional[int] = None) -> Dict[str, Any]:
        pool = db_utils.get_pool()
        if pool is None:
            return add_unopened_crate(user_id, crate_type)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO unopened_crates (owner_id, crate_type, transferable, gifted_from, created_at) VALUES ($1,$2,TRUE,$3,now()) RETURNING id",
                user_id,
                crate_type,
                gifted_from,
            )
            return {"crate_id": row["id"], "crate_type": crate_type}


    async def async_list_unopened_crates(user_id: int) -> List[Dict[str, Any]]:
        pool = db_utils.get_pool()
        if pool is None:
            return list_unopened_crates(user_id)

        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, crate_type, transferable, gifted_from, created_at FROM unopened_crates WHERE owner_id = $1 ORDER BY created_at DESC", user_id)
            return [{"crate_id": r["id"], "crate_type": r["crate_type"], "transferable": r["transferable"]} for r in rows]


    async def async_consume_unopened_crate(user_id: int, crate_type: str) -> Optional[Dict[str, Any]]:
        pool = db_utils.get_pool()
        if pool is None:
            return consume_unopened_crate(user_id, crate_type)

        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT id FROM unopened_crates WHERE owner_id = $1 AND crate_type = $2 ORDER BY created_at LIMIT 1 FOR UPDATE", user_id, crate_type)
                if row is None:
                    return None
                await conn.execute("DELETE FROM unopened_crates WHERE id = $1", row["id"])
                return {"crate_id": row["id"], "crate_type": crate_type}


    async def async_record_crate_opening(user_id: int, guild_id: Optional[int], crate_type: str, coins: int, items: List[Dict[str, Any]]) -> None:
        pool = db_utils.get_pool()
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO crate_openings (user_id, guild_id, crate_type, coins, items, created_at) VALUES ($1,$2,$3,$4,$5,now())",
                               user_id, guild_id, crate_type, coins, json.dumps(items))

    """Add an unopened crate to a user's inventory.

    Returns the crate dict.
    """
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        crate_id = int(time.time() * 1000)
        crate = {"crate_id": crate_id, "crate_type": crate_type}
        bucket.setdefault("unopened_crates", []).append(crate)
        _save_all(data)
        return crate


def list_unopened_crates(user_id: int) -> List[Dict[str, Any]]:
    data = _load_all()
    bucket = data.get(str(user_id), {})
    return bucket.get("unopened_crates", [])


def consume_unopened_crate(user_id: int, crate_type: str) -> Optional[Dict[str, Any]]:
    """Consume (remove) a single unopened crate of the given type for the user.

    Returns the consumed crate dict or None if none found.
    """
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        crates = bucket.setdefault("unopened_crates", [])
        for i, c in enumerate(crates):
            if c.get("crate_type") == crate_type:
                removed = crates.pop(i)
                bucket["unopened_crates"] = crates
                data[str(user_id)] = bucket
                _save_all(data)
                return removed
    return None
>>>>>>> Cursor-Branch
