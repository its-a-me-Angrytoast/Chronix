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
    data = _load_all()
    # Ensure we have a compact, forward-compatible bucket structure
    return data.setdefault(
        str(user_id), {"gems": [], "pets": [], "items": [], "unopened_crates": []}
    )


def add_gem(user_id: int, gem_type: str, power: int = 1) -> Dict[str, Any]:
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": []})
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
    """Merge `count` gems of same type into a stronger gem.

    Strategy: pick the `count` lowest-power gems of the specified type,
    remove them, and create a new gem with power = max_power + 1.
    """
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(user_id), {"gems": [], "pets": []})
        gems = [g for g in bucket.get("gems", []) if g.get("gem_type") == gem_type]
        if len(gems) < count:
            raise ValueError("Not enough gems to merge")
        # sort by power ascending and pick first `count`
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
    """Add a generic item to a user's inventory (misc items).

    Stores an item dict with an id, name and optional meta information.
    """
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
