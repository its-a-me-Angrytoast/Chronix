"""Deterministic battle engine used by Chronix battler cogs.

Provides a simple deterministic resolver function that accepts a seed
to make outcomes repeatable for tests. The production commands may call
the engine with a non-deterministic seed (e.g., time-based).
"""
from __future__ import annotations

from typing import Dict, Any, List, Tuple
import random
import math


def compute_damage(attacker_attack: int, defender_defense: int, gem_bonus: float = 0.0, affinity: float = 1.0, rng: random.Random | None = None) -> int:
    if rng is None:
        rng = random.Random()
    variability = 1.0 + rng.random() * 0.15  # up to +15%
    base = (attacker_attack - int(defender_defense * 0.3))
    if base < 1:
        base = 1
    dmg = math.floor(base * (1.0 + gem_bonus) * affinity * variability)
    return int(dmg)


def resolve_turn(attacker: Dict[str, Any], defender: Dict[str, Any], rng: random.Random | None = None) -> Tuple[int, int]:
    """Resolve a single turn: returns (damage_to_defender, damage_to_attacker)

    attacker and defender are normalized dicts with at least keys:
    - 'attack'
    - 'defense'
    - 'gems' (list of gem dicts with 'power')
    - 'affinity' (float)
    """
    if rng is None:
        rng = random.Random()
    gem_bonus_att = sum([g.get('power', 0) * 0.01 for g in attacker.get('gems', [])])
    gem_bonus_def = sum([g.get('power', 0) * 0.01 for g in defender.get('gems', [])])
    dmg_a = compute_damage(attacker.get('attack', 1), defender.get('defense', 0), gem_bonus_att, attacker.get('affinity', 1.0), rng)
    dmg_b = compute_damage(defender.get('attack', 1), attacker.get('defense', 0), gem_bonus_def, defender.get('affinity', 1.0), rng)
    return dmg_a, dmg_b


def run_battle(team_a: List[Dict[str, Any]], team_b: List[Dict[str, Any]], seed: int | None = None, max_rounds: int = 20) -> Dict[str, Any]:
    """Run a simple turn-based battle between two teams.

    Each team is a list of combatant dicts with fields: 'id', 'attack', 'defense', 'hp', 'gems', 'affinity'. Returns a summary dict describing winner and per-round events.
    If seed is provided, RNG is deterministic for tests.
    """
    rng = random.Random(seed)
    a = [dict(c) for c in team_a]
    b = [dict(c) for c in team_b]
    events = []
    round_no = 0
    while round_no < max_rounds and any(x.get('hp', 0) > 0 for x in a) and any(x.get('hp', 0) > 0 for x in b):
        round_no += 1
        # each side's lead combatant
        ca = next((x for x in a if x.get('hp', 0) > 0), None)
        cb = next((x for x in b if x.get('hp', 0) > 0), None)
        if ca is None or cb is None:
            break
        dmg_a, dmg_b = resolve_turn(ca, cb, rng)
        cb['hp'] = max(0, int(cb.get('hp', 0)) - dmg_a)
        ca['hp'] = max(0, int(ca.get('hp', 0)) - dmg_b)
        events.append({'round': round_no, 'attacker': ca.get('id'), 'defender': cb.get('id'), 'dmg_to_def': dmg_a, 'dmg_to_att': dmg_b, 'hp_a': ca['hp'], 'hp_b': cb['hp']})
    # decide winner
    alive_a = sum(1 for x in a if x.get('hp', 0) > 0)
    alive_b = sum(1 for x in b if x.get('hp', 0) > 0)
    if alive_a > alive_b:
        winner = 'A'
    elif alive_b > alive_a:
        winner = 'B'
    else:
        winner = 'draw'
    return {'winner': winner, 'alive_a': alive_a, 'alive_b': alive_b, 'rounds': round_no, 'events': events}
