"""Gameplay battles cog (file-backed support). This cog exposes commands for PvE and PvP battles.

This module avoids hard Discord API coupling where possible so tests can import
the core functions. If `discord` is available, the commands will be registered.
"""
from __future__ import annotations

import uuid
from typing import Optional

try:
    import discord
    from discord.ext import commands
except Exception:  # pragma: no cover - optional import
    discord = None
    commands = None

from chronix_bot.utils import battle_engine, enemies, battle_logs, battle_renderer
from chronix_bot.utils import rewards


def start_pve_battle_stub(user_id: int, template: str = "goblin", level: int = 1, seed: Optional[int] = None) -> dict:
    """Start a PvE battle programmatically (returns battle result)."""
    enemy = enemies.generate_enemy(template=template, level=level, seed=seed)
    # build teams
    team_user = [{"id": f"u{user_id}", "attack": 20, "defense": 5, "hp": 120, "gems": [], "affinity": 1.0}]
    team_enemy = [{"id": f"e_{enemy['template']}", "attack": enemy['attack'], "defense": enemy['defense'], "hp": enemy['hp'], "gems": [], "affinity": 1.0}]
    bid = str(uuid.uuid4())
    out = battle_engine.run_battle(team_user, team_enemy, seed=seed)
    # persist
    log_entry = {"battle_id": bid, "type": "pve", "user_id": user_id, "enemy": enemy, "result": out}
    battle_logs.append_battle_log(log_entry)
    # award rewards if user won
    if out.get('winner') == 'A':
        loot = enemies.roll_loot(enemy, seed=seed)
        rewards.award_coins(user_id, int(loot.get('coins', 0)))
        rewards.award_xp(user_id, int(enemy.get('exp', 0)))
        log_entry['awarded'] = {'coins': loot.get('coins', 0), 'xp': enemy.get('exp', 0)}
    return log_entry


if commands is not None:
    from typing import Any

    from typing import Any

    class Battles(commands.Cog):
        """Battle commands for Chronix."""

        def __init__(self, bot: Any):
            self.bot = bot

        @commands.command(name="battle", aliases=["fight", "duel"])  # prefix command
        async def battle(self, ctx: Any, target: Optional[Any] = None):
            """Start a PvP duel with another player or a PvE encounter if no target."""
            if target is None:
                # PvE
                entry = start_pve_battle_stub(ctx.author.id)
                frames = battle_renderer.render_battle_frames(entry['result']['events'])
                # send condensed result
                await ctx.send(f"Battle complete: {entry['result']['winner']} — rounds: {entry['result']['rounds']}")
                return
            # PvP placeholder: create two simple combatants and run
            team_a = [{"id": f"u{ctx.author.id}", "attack": 30, "defense": 8, "hp": 120, "gems": [], "affinity": 1.0}]
            team_b = [{"id": f"u{target.id}", "attack": 28, "defense": 7, "hp": 110, "gems": [], "affinity": 1.0}]
            out = battle_engine.run_battle(team_a, team_b)
            bid = str(uuid.uuid4())
            log_entry = {"battle_id": bid, "type": "pvp", "a": ctx.author.id, "b": target.id, "result": out}
            battle_logs.append_battle_log(log_entry)
            await ctx.send(f"Duel complete: {out['winner']} — rounds: {out['rounds']}")


    def setup(bot):
        if commands is not None:
            bot.add_cog(Battles(bot))
