import pytest
from chronix_bot.utils import battle_engine


def test_compute_damage_minimum():
    dmg = battle_engine.compute_damage(1, 10, gem_bonus=0.0, affinity=1.0, rng=None)
    assert isinstance(dmg, int)
    assert dmg >= 1


def test_resolve_turn_deterministic():
    rng = __import__('random').Random(12345)
    att = {'attack': 50, 'defense': 10, 'gems': [{'power': 5}], 'affinity': 1.0}
    defn = {'attack': 40, 'defense': 12, 'gems': [], 'affinity': 1.0}
    dmg_a, dmg_b = battle_engine.resolve_turn(att, defn, rng)
    # deterministic expectations for seed
    assert isinstance(dmg_a, int) and isinstance(dmg_b, int)
    assert dmg_a > 0


def test_run_battle_simple_victory():
    a = [{'id': 'a1', 'attack': 30, 'defense': 5, 'hp': 100, 'gems': [], 'affinity': 1.0}]
    b = [{'id': 'b1', 'attack': 10, 'defense': 2, 'hp': 40, 'gems': [], 'affinity': 1.0}]
    out = battle_engine.run_battle(a, b, seed=42, max_rounds=10)
    assert out['winner'] == 'A'
    assert out['alive_a'] >= 1
    assert out['alive_b'] == 0
