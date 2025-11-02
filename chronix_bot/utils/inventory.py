"""Simple inventory persistence for Phase 4.

Provides a lightweight file-backed inventory store used by gameplay cogs.
This module now exposes both synchronous file-backed helpers (used in
development) and async DB-backed helpers that will be used when a
Postgres pool is initialized. The async helpers fall back to the
synchronous file-backed implementations when no DB pool is available.

APIs provided (sync):
- add_gem, list_gems, add_pet, list_pets, add_item, list_items,
  add_unopened_crate, list_unopened_crates, consume_unopened_crate

APIs provided (async DB-aware):
- async_add_item, async_add_unopened_crate, async_list_unopened_crates,
  async_consume_unopened_crate, async_record_crate_opening
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Dict, Any, List, Optional
import yaml
import random

from chronix_bot.utils import db as db_utils

DATA_DIR = Path.cwd() / "data"
INVENTORY_FILE = DATA_DIR / "inventories.json"
_lock = threading.Lock()
SPEC_FILE = DATA_DIR / "pet_species.yaml"
_sr = random.SystemRandom()


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


def add_pet(user_id: int, species: str) -> Dict[str, Any]:
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        pet_id = int(time.time() * 1000)
        # Load species defaults (if available) to assign rarity/traits
        rarity = "common"
        traits: List[str] = []
        image = ""
        try:
            if SPEC_FILE.exists():
                spec = yaml.safe_load(SPEC_FILE.read_text(encoding="utf-8")) or {}
                sdef = spec.get(species, {})
                if sdef:
                    rarity = sdef.get("rarity", rarity)
                    traits = list(sdef.get("traits", []))
                    image = sdef.get("image", "") or ""
        except Exception:
            pass

        # If species has no explicit rarity, pick from weighted distribution
        if rarity == "common":
            rarity = _sr.choices(["common", "uncommon", "rare", "epic", "legendary"], weights=[60,25,10,4,1])[0]

        pet = {"pet_id": pet_id, "species": species, "level": 1, "xp": 0, "rarity": rarity, "traits": traits, "image": image, "wins": 0, "losses": 0}
        bucket.setdefault("pets", []).append(pet)
        _save_all(data)
        return pet


def list_pets(user_id: int) -> List[Dict[str, Any]]:
    data = _load_all()
    bucket = data.get(str(user_id), {})
    return bucket.get("pets", [])


def get_pet(user_id: int, pet_id: int) -> Optional[Dict[str, Any]]:
    data = _load_all()
    bucket = data.get(str(user_id), {})
    for p in bucket.get("pets", []):
        try:
            if int(p.get("pet_id")) == int(pet_id):
                return p
        except Exception:
            continue
    return None


def _save_pet_state(user_id: int, pets: List[Dict[str, Any]]) -> None:
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        bucket["pets"] = pets
        data[str(user_id)] = bucket
        _save_all(data)


def feed_pet(user_id: int, pet_id: int, xp: int = 20) -> Dict[str, Any]:
    """Feed a pet to grant XP and handle leveling.

    Leveling rule: required_xp = level * 100
    Returns updated pet dict or raises ValueError if not found.
    """
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        pets = bucket.setdefault("pets", [])
        for p in pets:
            try:
                if int(p.get("pet_id")) == int(pet_id):
                    p["xp"] = int(p.get("xp", 0)) + int(xp)
                    # level up loop
                    leveled = False
                    while True:
                        lvl = int(p.get("level", 1))
                        needed = lvl * 100
                        if int(p.get("xp", 0)) >= needed:
                            p["xp"] = int(p.get("xp", 0)) - needed
                            p["level"] = lvl + 1
                            leveled = True
                            continue
                        break
                    bucket["pets"] = pets
                    data[str(user_id)] = bucket
                    _save_all(data)
                    # write pet log
                    try:
                        DATA_DIR.mkdir(parents=True, exist_ok=True)
                        plf = DATA_DIR / "pet_logs.jsonl"
                        entry = {"user_id": int(user_id), "pet_id": int(pet_id), "action": "feed", "xp": int(xp), "level": int(p.get("level", 1)), "ts": int(time.time())}
                        with open(plf, "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(entry) + "\n")
                    except Exception:
                        pass
                    return p
            except Exception:
                continue
    raise ValueError("Pet not found")


def release_pet(user_id: int, pet_id: int) -> Optional[Dict[str, Any]]:
    """Release (remove) a pet from a user's inventory. Returns removed pet or None."""
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        pets = bucket.setdefault("pets", [])
        for i, p in enumerate(pets):
            try:
                if int(p.get("pet_id")) == int(pet_id):
                    removed = pets.pop(i)
                    bucket["pets"] = pets
                    data[str(user_id)] = bucket
                    _save_all(data)
                    try:
                        DATA_DIR.mkdir(parents=True, exist_ok=True)
                        plf = DATA_DIR / "pet_logs.jsonl"
                        entry = {"user_id": int(user_id), "pet_id": int(pet_id), "action": "release", "ts": int(time.time())}
                        with open(plf, "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(entry) + "\n")
                    except Exception:
                        pass
                    return removed
            except Exception:
                continue
    return None


def record_battle_result(user_id: int, pet_id: int, result: str, opponent: Optional[Dict[str, Any]] = None, xp: int = 0, coins: int = 0) -> None:
    """Record a battle result for a pet and update wins/losses and XP.

    result: one of 'win', 'loss', 'draw'
    """
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []})
        pets = bucket.setdefault("pets", [])
        for p in pets:
            try:
                if int(p.get("pet_id")) == int(pet_id):
                    if result == "win":
                        p["wins"] = int(p.get("wins", 0)) + 1
                    elif result == "loss":
                        p["losses"] = int(p.get("losses", 0)) + 1
                    # award XP
                    if xp:
                        p["xp"] = int(p.get("xp", 0)) + int(xp)
                        # handle level ups
                        while True:
                            lvl = int(p.get("level", 1))
                            needed = lvl * 100
                            if int(p.get("xp", 0)) >= needed:
                                p["xp"] = int(p.get("xp", 0)) - needed
                                p["level"] = lvl + 1
                                continue
                            break
                    data[str(user_id)] = bucket
                    _save_all(data)
                    # log entry
                    try:
                        DATA_DIR.mkdir(parents=True, exist_ok=True)
                        plf = DATA_DIR / "pet_logs.jsonl"
                        entry = {"user_id": int(user_id), "pet_id": int(pet_id), "action": "battle", "result": result, "opponent": opponent or {}, "xp": int(xp), "coins": int(coins), "ts": int(time.time())}
                        with open(plf, "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(entry) + "\n")
                    except Exception:
                        pass
                    return
            except Exception:
                continue


def pet_leaderboard(top: int = 10, by: str = "level") -> List[Dict[str, Any]]:
    """Return top pets across all users by 'level' or 'wins'."""
    out = []
    data = _load_all()
    for uid, bucket in data.items():
        for p in bucket.get("pets", []):
            try:
                if by == "level":
                    score = int(p.get("level", 1))
                else:
                    score = int(p.get("wins", 0))
                out.append({"user_id": int(uid), "pet": p, "score": score})
            except Exception:
                continue
    out.sort(key=lambda r: r.get("score", 0), reverse=True)
    return out[:top]


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


### Async DB-backed helpers (fall back to file-backed when no DB pool) ###


async def async_add_unopened_crate(user_id: int, crate_type: str) -> Dict[str, Any]:
    pool = db_utils.get_pool()
    if pool is None:
        return add_unopened_crate(user_id, crate_type)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO unopened_crates (owner_id, crate_type) VALUES ($1, $2) RETURNING id, crate_type",
            user_id,
            crate_type,
        )
        return {"crate_id": int(row["id"]), "crate_type": row["crate_type"]}


async def async_list_unopened_crates(user_id: int) -> List[Dict[str, Any]]:
    pool = db_utils.get_pool()
    if pool is None:
        return list_unopened_crates(user_id)

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, crate_type FROM unopened_crates WHERE owner_id = $1 ORDER BY created_at", user_id)
        return [{"crate_id": int(r["id"]), "crate_type": r["crate_type"]} for r in rows]


async def async_consume_unopened_crate(user_id: int, crate_type: str) -> Optional[Dict[str, Any]]:
    pool = db_utils.get_pool()
    if pool is None:
        return consume_unopened_crate(user_id, crate_type)

    # Atomically select one unopened crate and remove it inside a transaction
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, crate_type FROM unopened_crates WHERE owner_id = $1 AND crate_type = $2 ORDER BY created_at LIMIT 1 FOR UPDATE",
                user_id,
                crate_type,
            )
            if row is None:
                return None
            crate_id = int(row["id"])
            await conn.execute("DELETE FROM unopened_crates WHERE id = $1", crate_id)
            return {"crate_id": crate_id, "crate_type": row["crate_type"]}


async def async_add_item(user_id: int, name: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    pool = db_utils.get_pool()
    if pool is None:
        return add_item(user_id, name, meta)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO user_items (user_id, item_type, name, meta) VALUES ($1, $2, $3, $4) RETURNING id",
            user_id,
            meta.get("type") if meta else "misc",
            name,
            json.dumps(meta or {}),
        )
        return {"item_id": int(row["id"]), "name": name, "meta": meta or {}}


async def async_record_crate_opening(user_id: int, guild_id: Optional[int], crate_type: str, coins: int, items: List[Dict[str, Any]]) -> None:
    pool = db_utils.get_pool()
    if pool is None:
        # fallback: append to file-backed 'crate_openings.log' for dev
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        logf = DATA_DIR / "crate_openings.jsonl"
        entry = {
            "user_id": int(user_id),
            "guild_id": int(guild_id) if guild_id is not None else None,
            "crate_type": crate_type,
            "coins": int(coins),
            "items": items,
            "created_at": int(time.time()),
        }
        with open(logf, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO crate_openings (user_id, guild_id, crate_type, coins, items) VALUES ($1, $2, $3, $4, $5)",
            user_id,
            guild_id,
            crate_type,
            coins,
            json.dumps(items),
        )

