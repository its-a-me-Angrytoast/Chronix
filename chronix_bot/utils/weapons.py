"""Weapon utilities for Chronix (file-backed with DB-aware placeholders).

Provides simple weapon creation, equip/unequip, inspection and basic
upgrade/forge operations. Designed to be file-backed so the project can
run in development without a DB.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_DIR = Path.cwd() / "data"
WEAPONS_FILE = DATA_DIR / "weapons.json"
_lock = threading.Lock()


def _load_all() -> Dict[str, Any]:
    if not WEAPONS_FILE.exists():
        return {}
    try:
        return json.loads(WEAPONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEAPONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def create_weapon(owner_id: int, name: str, wtype: str = "sword", attack: int = 5, rarity: str = "common", element: Optional[str] = None, slots: int = 0) -> Dict[str, Any]:
    """Create a weapon entry and assign to a user (file-backed).

    Returns the weapon dict.
    """
    with _lock:
        data = _load_all()
        owners = data.setdefault(str(owner_id), {"weapons": []})
        wid = int(time.time() * 1000)
        weapon = {
            "weapon_id": wid,
            "name": name,
            "type": wtype,
            "attack": int(attack),
            "rarity": rarity,
            "element": element,
            "slots": int(slots),
            "gems": [],
            "equipped": False,
            "durability": 100,
            "max_durability": 100,
            "created_at": int(time.time()),
        }
        owners.setdefault("weapons", []).append(weapon)
        data[str(owner_id)] = owners
        _save_all(data)
        return weapon


def list_weapons(owner_id: int) -> List[Dict[str, Any]]:
    data = _load_all()
    bucket = data.get(str(owner_id), {})
    return bucket.get("weapons", [])


def get_weapon(owner_id: int, weapon_id: int) -> Optional[Dict[str, Any]]:
    for w in list_weapons(owner_id):
        try:
            if int(w.get("weapon_id")) == int(weapon_id):
                return w
        except Exception:
            continue
    return None


def equip_weapon(owner_id: int, weapon_id: int) -> bool:
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(owner_id), {"weapons": []})
        weapons = bucket.setdefault("weapons", [])
        for w in weapons:
            try:
                if int(w.get("weapon_id")) == int(weapon_id):
                    # unequip others
                    for o in weapons:
                        o["equipped"] = False
                    w["equipped"] = True
                    data[str(owner_id)] = bucket
                    _save_all(data)
                    return True
            except Exception:
                continue
    return False


def unequip_weapon(owner_id: int) -> bool:
    with _lock:
        data = _load_all()
        bucket = data.setdefault(str(owner_id), {"weapons": []})
        weapons = bucket.setdefault("weapons", [])
        changed = False
        for w in weapons:
            if w.get("equipped"):
                w["equipped"] = False
                changed = True
        if changed:
            data[str(owner_id)] = bucket
            _save_all(data)
        return changed


def inspect_weapon(owner_id: int, weapon_id: int) -> Optional[Dict[str, Any]]:
    return get_weapon(owner_id, weapon_id)


def upgrade_weapon(owner_id: int, weapon_id: int, increase: int = 1) -> Optional[Dict[str, Any]]:
    with _lock:
        w = get_weapon(owner_id, weapon_id)
        if not w:
            return None
        try:
            w["attack"] = int(w.get("attack", 0)) + int(increase)
            # upgrading reduces durability slightly
            w["durability"] = max(1, int(w.get("durability", 0)) - int(max(1, int(increase) * 2)))
            data = _load_all()
            bucket = data.setdefault(str(owner_id), {"weapons": []})
            # replace weapon in list
            for i, it in enumerate(bucket.setdefault("weapons", [])):
                if int(it.get("weapon_id")) == int(weapon_id):
                    bucket["weapons"][i] = w
                    break
            data[str(owner_id)] = bucket
            _save_all(data)
            return w
        except Exception:
            return None


def add_gem_to_weapon(owner_id: int, weapon_id: int, gem: Dict[str, Any]) -> bool:
    with _lock:
        w = get_weapon(owner_id, weapon_id)
        if not w:
            return False
        slots = int(w.get("slots", 0))
        if len(w.get("gems", [])) >= slots:
            return False
        w.setdefault("gems", []).append(gem)
        data = _load_all()
        bucket = data.setdefault(str(owner_id), {"weapons": []})
        for i, it in enumerate(bucket.setdefault("weapons", [])):
            if int(it.get("weapon_id")) == int(weapon_id):
                bucket["weapons"][i] = w
                break
        data[str(owner_id)] = bucket
        _save_all(data)
        return True


def reduce_durability(owner_id: int, weapon_id: int, amount: int = 1) -> bool:
    with _lock:
        w = get_weapon(owner_id, weapon_id)
        if not w:
            return False
        w["durability"] = max(0, int(w.get("durability", 0)) - int(amount))
        data = _load_all()
        bucket = data.setdefault(str(owner_id), {"weapons": []})
        for i, it in enumerate(bucket.setdefault("weapons", [])):
            if int(it.get("weapon_id")) == int(weapon_id):
                bucket["weapons"][i] = w
                break
        data[str(owner_id)] = bucket
        _save_all(data)
        return True


def repair_weapon(owner_id: int, weapon_id: int, restore_to: int | None = None) -> Optional[int]:
    """Repairs a weapon and returns the estimated cost (file-backed). Does not deduct coins here.

    If restore_to is None, restore to max_durability; otherwise restore to that value.
    """
    with _lock:
        w = get_weapon(owner_id, weapon_id)
        if not w:
            return None
        max_d = int(w.get("max_durability", 100))
        target = int(restore_to) if restore_to is not None else max_d
        target = min(target, max_d)
        cur = int(w.get("durability", 0))
        if target <= cur:
            return 0
        diff = target - cur
        # cost formula: 1 chron per durability point by default
        cost = diff * 1
        w["durability"] = target
        data = _load_all()
        bucket = data.setdefault(str(owner_id), {"weapons": []})
        for i, it in enumerate(bucket.setdefault("weapons", [])):
            if int(it.get("weapon_id")) == int(weapon_id):
                bucket["weapons"][i] = w
                break
        data[str(owner_id)] = bucket
        _save_all(data)
        return cost
