"""Simple inventory persistence for Phase 4.

Provides a lightweight file-backed inventory store used by gameplay cogs.
This file contains synchronous helpers only; DB-backed async helpers can
be added later if/when a database is configured.

APIs used by other cogs:
- add_gem(user_id, gem_type, power) -> gem dict
- add_pet(user_id, species) -> pet dict
- add_item(user_id, name, meta) -> item dict
- add_unopened_crate(user_id, crate_type) -> crate dict
- list_unopened_crates(user_id) -> list[dict]
- list_items(user_id) -> list[dict]
- consume_unopened_crate(user_id, crate_type) -> optional crate dict
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
        pet = {"pet_id": pet_id, "species": species, "level": 1, "xp": 0}
        bucket.setdefault("pets", []).append(pet)
        _save_all(data)
        return pet


def list_pets(user_id: int) -> List[Dict[str, Any]]:
    data = _load_all()
    bucket = data.get(str(user_id), {})
    return bucket.get("pets", [])


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
