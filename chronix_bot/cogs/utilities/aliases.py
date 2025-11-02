"""Aliases manager cog (file-backed).

Provides admin commands to create, remove, list, and execute named aliases.
Aliases map a short name to a full command string (prefix-included or not).
This is a simple, safe manager: it does not rewrite arbitrary user messages.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import helpers


DATA_DIR = Path.cwd() / "data"
ALIASES_FILE = DATA_DIR / "aliases.json"


def _load_aliases() -> dict:
    if not ALIASES_FILE.exists():
        return {}
    try:
        return json.loads(ALIASES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_aliases(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ALIASES_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


class Aliases(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="alias_add")
    @commands.has_permissions(manage_guild=True)
    async def alias_add(self, ctx: commands.Context, name: str, *, command_text: str):
        """Add an alias: chro alias_add greet "chro say Hello!""" 
        d = _load_aliases()
        gid = str(ctx.guild.id if ctx.guild else 0)
        g = d.setdefault(gid, {})
        g[name] = command_text
        d[gid] = g
        _save_aliases(d)
        await ctx.send(embed=helpers.make_embed("Alias Added", f"{name} -> {command_text}"))

    @commands.command(name="alias_remove")
    @commands.has_permissions(manage_guild=True)
    async def alias_remove(self, ctx: commands.Context, name: str):
        d = _load_aliases()
        gid = str(ctx.guild.id if ctx.guild else 0)
        g = d.get(gid, {})
        if name in g:
            del g[name]
            d[gid] = g
            _save_aliases(d)
            await ctx.send(embed=helpers.make_embed("Alias Removed", f"Removed {name}"))
            return
        await ctx.send("Alias not found.")

    @commands.command(name="alias_list")
    @commands.has_permissions(manage_guild=True)
    async def alias_list(self, ctx: commands.Context):
        d = _load_aliases()
        gid = str(ctx.guild.id if ctx.guild else 0)
        g = d.get(gid, {})
        if not g:
            await ctx.send("No aliases configured for this guild.")
            return
        lines = [f"{k}: {v}" for k, v in g.items()]
        await ctx.send(embed=helpers.make_embed("Aliases", "\n".join(lines)))

    @commands.command(name="alias_exec")
    async def alias_exec(self, ctx: commands.Context, name: str, *, extra: Optional[str] = ""):
        """Execute a configured alias as the invoking user. Use with caution."""
        d = _load_aliases()
        gid = str(ctx.guild.id if ctx.guild else 0)
        g = d.get(gid, {})
        if name not in g:
            await ctx.send("Alias not found.")
            return
        cmd = g[name]
        # append extra args if provided
        if extra:
            cmd = f"{cmd} {extra}"
        # send the resolved command as if the user typed it (prefix expected)
        # we cannot impersonate the user; instead, we instruct the bot to process the command content
        # by creating a new message-like object and calling process_commands.
        fake = ctx.message
        # monkeypatch content temporarily (safe because commands are synchronous here)
        old_content = fake.content
        try:
            fake.content = cmd
            await ctx.bot.process_commands(fake)
        finally:
            fake.content = old_content


async def setup(bot: commands.Bot):
    await bot.add_cog(Aliases(bot))
