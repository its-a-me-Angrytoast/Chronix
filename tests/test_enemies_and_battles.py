from chronix_bot.utils import enemies, battle_engine, battle_logs


def test_generate_enemy_scaling():
    e1 = enemies.generate_enemy("goblin", level=1, seed=42)
    e5 = enemies.generate_enemy("goblin", level=5, seed=42)
    assert e5['hp'] >= e1['hp']


def test_roll_loot_has_structure():
    e = enemies.generate_enemy("orc", level=3, seed=7)
    loot = enemies.roll_loot(e, seed=8)
    assert 'coins' in loot and isinstance(loot['coins'], int)


def test_battle_log_append_and_read(tmp_path):
    # write to repo data path by calling append and reading back
    entry = {'battle_id': 'test123', 'type': 'unit', 'result': {'winner': 'A', 'events': []}}
    battle_logs.append_battle_log(entry)
    found = battle_logs.get_log_by_id('test123')
    assert found is not None and found.get('battle_id') == 'test123'
