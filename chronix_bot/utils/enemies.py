"""Enemy generator and loot integration for Chronix.

File-backed and deterministic when given a seed. Provides simple
enemy templates and a loot roll function.
"""
from __future__ import annotations

from typing import Dict, Any, Optional
import json
from pathlib import Path
import random
import time

DATA_DIR = Path.cwd() / "data"
ENEMIES_FILE = DATA_DIR / "enemies.json"
LOOT_FILE = DATA_DIR / "loot_overrides.json"


def _load_enemies() -> Dict[str, Any]:
    if not ENEMIES_FILE.exists():
        # create reasonable defaults
        default = {
            "goblin": {"base_hp": 30, "base_att": 6, "base_def": 2, "exp": 10, "coins": 5},
            "orc": {"base_hp": 70, "base_att": 12, "base_def": 5, "exp": 25, "coins": 20},
            "wyrm": {"base_hp": 200, "base_att": 35, "base_def": 12, "exp": 100, "coins": 80},
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ENEMIES_FILE.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default
    try:
        return json.loads(ENEMIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_loot_overrides() -> Dict[str, Any]:
    if not LOOT_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOOT_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")
        return {}
    try:
        return json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def generate_enemy(template: str = "goblin", level: int = 1, seed: Optional[int] = None) -> Dict[str, Any]:
    """Generate an enemy dict scaled by level. Deterministic when seed provided."""
    rng = random.Random(seed if seed is not None else int(time.time() * 1000))
    templates = _load_enemies()
    tpl = templates.get(template)
    if not tpl:
        # fallback to goblin
        tpl = templates.get("goblin")
    hp = int(tpl.get("base_hp", 10) * (1 + (level - 1) * 0.25))
    attack = int(tpl.get("base_att", 1) * (1 + (level - 1) * 0.18))
    defense = int(tpl.get("base_def", 0) * (1 + (level - 1) * 0.12))
    # small variance
    hp = max(1, int(hp * (0.9 + rng.random() * 0.2)))
    attack = max(1, int(attack * (0.9 + rng.random() * 0.2)))
    defense = max(0, int(defense * (0.9 + rng.random() * 0.2)))
    return {
        "template": template,
        "level": int(level),
        "hp": hp,
        "attack": attack,
        "defense": defense,
        "exp": int(tpl.get("exp", 1) * level),
        "coins": int(tpl.get("coins", 1) * level),
    }


def roll_loot(enemy: Dict[str, Any], seed: Optional[int] = None) -> Dict[str, Any]:
    """Roll loot for a defeated enemy. Returns dict with 'coins', 'items' list and 'gems' list."""
    rng = random.Random(seed if seed is not None else int(time.time() * 1000))
    loot_overrides = _load_loot_overrides()
    template = enemy.get("template")
    base_coins = int(enemy.get("coins", 0))
    coins = int(base_coins * (0.8 + rng.random() * 0.5))
    items = []
    gems = []
    # small chance for gem
    if rng.random() < min(0.05 + (enemy.get("level", 1) * 0.01), 0.5):
        gems.append({"gem_type": "basic", "power": rng.randint(1, 6)})
    # override special drops from file
    if template in loot_overrides:
        lo = loot_overrides[template]
        if rng.random() < lo.get("rare_chance", 0.0):
            items.append(lo.get("rare_item"))
    return {"coins": coins, "items": items, "gems": gems}
