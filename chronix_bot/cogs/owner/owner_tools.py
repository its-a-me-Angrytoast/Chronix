"""Owner and developer tools (Phase 3).

Provides owner-only commands: eval, exec, load, unload, reload, toggle feature,
hot-reload, sysinfo, and simple DB control helpers. All commands are owner-only
and log actions to the async logger.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import textwrap
import traceback
from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import logger as chronix_logger
from chronix_bot.utils import db as db_utils


class OwnerTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _log_action(self, action: str, detail: Optional[dict] = None) -> None:
        chronix_logger.enqueue_log({"type": "owner_action", "action": action, "detail": detail})

    @commands.is_owner()
    @commands.command(name="eval")
    async def _eval(self, ctx: commands.Context, *, body: str) -> None:
        """Evaluate Python code (owner-only)."""
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "asyncio": asyncio,
        }
        body = body.strip("` \n")
        try:
            result = eval(body, env)
            await ctx.send(f"Eval result: {result}")
            self._log_action("eval", {"user": ctx.author.id, "body": body})
        except Exception as e:
            await ctx.send(f"Eval error: {e}")
            self._log_action("eval_error", {"user": ctx.author.id, "error": str(e)})

    @commands.is_owner()
    @commands.command(name="exec")
    async def _exec(self, ctx: commands.Context, *, body: str) -> None:
        """Execute Python code block (owner-only)."""
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "asyncio": asyncio,
        }
        body = body.strip("` \n")
        try:
            exec(body, env)
            await ctx.send("Executed.")
            self._log_action("exec", {"user": ctx.author.id, "body": body})
        except Exception as e:
            await ctx.send(f"Exec error: {e}")
            self._log_action("exec_error", {"user": ctx.author.id, "error": str(e)})

    @commands.is_owner()
    @commands.command(name="reload")
    async def reload_ext(self, ctx: commands.Context, *, extension: str) -> None:
        try:
            self.bot.reload_extension(extension)
            await ctx.send(f"Reloaded {extension}")
            self._log_action("reload", {"extension": extension})
        except Exception as e:
            await ctx.send(f"Reload failed: {e}")
            self._log_action("reload_failed", {"extension": extension, "error": str(e)})

    @commands.is_owner()
    @commands.command(name="load")
    async def load_ext(self, ctx: commands.Context, *, extension: str) -> None:
        try:
            await self.bot.load_extension(extension)
            await ctx.send(f"Loaded {extension}")
            self._log_action("load", {"extension": extension})
        except Exception as e:
            await ctx.send(f"Load failed: {e}")
            self._log_action("load_failed", {"extension": extension, "error": str(e)})

    @commands.is_owner()
    @commands.command(name="unload")
    async def unload_ext(self, ctx: commands.Context, *, extension: str) -> None:
        try:
            await self.bot.unload_extension(extension)
            await ctx.send(f"Unloaded {extension}")
            self._log_action("unload", {"extension": extension})
        except Exception as e:
            await ctx.send(f"Unload failed: {e}")
            self._log_action("unload_failed", {"extension": extension, "error": str(e)})

    @commands.is_owner()
    @commands.command(name="toggle")
    async def toggle_feature(self, ctx: commands.Context, extension: str, mode: str) -> None:
        """Enable or disable a cog by extension path. mode: on/off."""
        mode = mode.lower()
        try:
            if mode in ("on", "enable"):
                await self.bot.load_extension(extension)
                await ctx.send(f"Enabled {extension}")
                self._log_action("enable_feature", {"extension": extension})
            else:
                await self.bot.unload_extension(extension)
                await ctx.send(f"Disabled {extension}")
                self._log_action("disable_feature", {"extension": extension})
        except Exception as e:
            await ctx.send(f"Toggle failed: {e}")
            self._log_action("toggle_failed", {"extension": extension, "error": str(e)})

    @commands.is_owner()
    @commands.command(name="hot_reload")
    async def hot_reload(self, ctx: commands.Context) -> None:
        """Reload all loaded extensions. Useful in dev mode."""
        reloaded = []
        failed = []
        for ext in list(self.bot.extensions.keys()):
            try:
                self.bot.reload_extension(ext)
                reloaded.append(ext)
            except Exception:
                failed.append(ext)
        await ctx.send(f"Reloaded: {len(reloaded)} extensions; Failed: {len(failed)}")
        self._log_action("hot_reload", {"reloaded": reloaded, "failed": failed})

    @commands.is_owner()
    @commands.command(name="sysinfo")
    async def sysinfo(self, ctx: commands.Context) -> None:
        """Return minimal system info (latency, loaded cogs)."""
        latency = round(self.bot.latency * 1000)
        exts = list(self.bot.extensions.keys())
        await ctx.send(f"Latency: {latency}ms\nLoaded extensions: {len(exts)}")

    @commands.is_owner()
    @commands.command(name="db_ping")
    async def db_ping(self, ctx: commands.Context) -> None:
        pool = db_utils.get_pool()
        if pool is None:
            await ctx.send("DB pool not configured (running in in-memory/dev mode)")
            return
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            await ctx.send("DB ping successful")
        except Exception as e:
            await ctx.send(f"DB ping failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(OwnerTools(bot))
