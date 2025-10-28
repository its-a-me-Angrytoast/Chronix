"""Loot generation utilities for gameplay (Phase 4).

This module loads `data/loot_tables.yaml` and provides a simple, secure
RNG-based loot generator used by the `hunt` and crate systems.

Design notes:
- Uses random.SystemRandom for secure RNG suitable for game rewards.
- Loads YAML tables lazily and falls back to a sensible default if the
  YAML file is missing or empty so the dev experience works out-of-the-box.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import random
import yaml

_RNG = random.SystemRandom()
_LOOT_PATH = Path("data/loot_tables.yaml")
_LOOT_CACHE: Optional[Dict[str, Any]] = None


def _load_tables() -> Dict[str, Any]:
    global _LOOT_CACHE
    if _LOOT_CACHE is not None:
        return _LOOT_CACHE

    if not _LOOT_PATH.exists():
        # Provide a reasonable default table
        _LOOT_CACHE = {
            "basic": {
                "coins": {"min": 10, "max": 100},
                "items": [
                    {"name": "Small Gem", "type": "gem", "rarity": "common", "weight": 70},
                    {"name": "Big Gem", "type": "gem", "rarity": "rare", "weight": 20},
                    {"name": "Stray Pet Egg", "type": "pet", "rarity": "uncommon", "weight": 10},
                ],
            }
        }
        return _LOOT_CACHE

    try:
        raw = yaml.safe_load(_LOOT_PATH.read_text()) or {}
    except Exception:
        raw = {}

    # Minimal validation and defaults
    if not isinstance(raw, dict) or not raw:
        _LOOT_CACHE = {
            "basic": {
                "coins": {"min": 10, "max": 100},
                "items": [
                    {"name": "Small Gem", "type": "gem", "rarity": "common", "weight": 70},
                    {"name": "Big Gem", "type": "gem", "rarity": "rare", "weight": 20},
                    {"name": "Stray Pet Egg", "type": "pet", "rarity": "uncommon", "weight": 10},
                ],
            }
        }
    else:
        _LOOT_CACHE = raw

    return _LOOT_CACHE


def _weighted_choice(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a single item chosen by the 'weight' key.

    Items without a numeric weight are treated as weight=1.
    Returns None if items list is empty.
    """
    if not items:
        return None
    weights = [float(item.get("weight", 1)) for item in items]
    total = sum(weights)
    if total <= 0:
        # fallback to first item
        return items[0]
    pick = _RNG.random() * total
    upto = 0.0
    for item, w in zip(items, weights):
        upto += w
        if pick <= upto:
            return item
    return items[-1]


def generate_loot(table: str = "basic") -> Dict[str, Any]:
    """Generate loot from a named table.

    Returns a dictionary with at least the `coins` integer and an `items`
    list describing dropped items.
    """
    tables = _load_tables()
    spec = tables.get(table)
    if spec is None:
        spec = tables.get("basic")

    # Coins
    coins_spec = spec.get("coins", {"min": 0, "max": 0})
    cmin = int(coins_spec.get("min", 0))
    cmax = int(coins_spec.get("max", cmin))
    coins = _RNG.randint(cmin, cmax)

    # Items: decide 0..N items, for now 0 or 1 item with weighted chance
    items_def = spec.get("items", [])
    drop = _weighted_choice(items_def)
    items: List[Dict[str, Any]] = []
    if drop is not None:
        # apply a simple drop chance derived from weight vs sum (already applied in weighted_choice)
        # We'll randomly decide whether the chosen item actually dropped, using a conservative multiplier.
        # This keeps most hunts yielding coins and occasional item drops.
        chance = min(0.40 + (drop.get("weight", 1) / 200.0), 0.95)
        if _RNG.random() < chance:
            items.append(drop.copy())

    return {"coins": coins, "items": items}


def reload_tables() -> None:
    """Clear cached tables so they will be reloaded on next generate call.

    Useful for development when editing YAML tables.
    """
    global _LOOT_CACHE
    _LOOT_CACHE = None
