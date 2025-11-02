from __future__ import annotations

from typing import Optional
import json
from pathlib import Path

import discord
from discord.ext import commands

from chronix_bot.utils import db as db_utils, helpers

DATA_DIR = Path.cwd() / "data"
EVENTS_FILE = DATA_DIR / "event_crates.json"


def _load_events() -> list:
    if not EVENTS_FILE.exists():
        return []
    try:
        return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_events(data: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


class EventAdmin(commands.Cog):
    """Admin commands to manage limited-time event crates.

    These commands write to the DB `event_crates` table when a pool exists,
    otherwise they persist to `data/event_crates.json`.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="create_event_crate")
    @commands.has_permissions(administrator=True)
    async def create_event_crate(self, ctx: commands.Context, name: str, crate_table: str, starts_at: Optional[str] = None, ends_at: Optional[str] = None):
        """Create an event crate entry.

        Example: chro create_event_crate spring_festival spring_pool 2025-12-01T00:00:00Z 2025-12-31T23:59:59Z
        """
        pool = db_utils.get_pool()
        if pool is not None:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO event_crates (name, crate_table, starts_at, ends_at, enabled) VALUES ($1, $2, $3, $4, $5)",
                    name,
                    crate_table,
                    starts_at,
                    ends_at,
                    True,
                )
            await ctx.send(embed=helpers.make_embed("Event crate created", f"{name} -> {crate_table} (enabled)"))
            return

        # file-backed fallback
        data = _load_events()
        entry = {"name": name, "crate_table": crate_table, "starts_at": starts_at, "ends_at": ends_at, "enabled": True}
        data.append(entry)
        _save_events(data)
        await ctx.send(embed=helpers.make_embed("Event crate created", f"{name} -> {crate_table} (file-backed)"))

    @commands.command(name="list_event_crates")
    async def list_event_crates(self, ctx: commands.Context):
        pool = db_utils.get_pool()
        if pool is not None:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT id, name, crate_table, starts_at, ends_at, enabled FROM event_crates ORDER BY created_at DESC")
                if not rows:
                    await ctx.send("No event crates found.")
                    return
                lines = [f"{r['id']}: {r['name']} -> {r['crate_table']} (enabled={r['enabled']})" for r in rows]
                await ctx.send(embed=helpers.make_embed("Event crates", "\n".join(lines)))
                return

        data = _load_events()
        if not data:
            await ctx.send("No event crates found.")
            return
        lines = [f"{i+1}: {e['name']} -> {e.get('crate_table')} (enabled={e.get('enabled')})" for i, e in enumerate(data)]
        await ctx.send(embed=helpers.make_embed("Event crates", "\n".join(lines)))


async def setup(bot: commands.Bot):
    await bot.add_cog(EventAdmin(bot))
