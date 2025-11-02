"""Bot factory for Chronix.

Creates and configures the commands.Bot instance and auto-loads the core cog.
"""
from typing import Optional, Set
import os
import time
import discord
from discord.ext import commands
from discord import Object
from .config import Settings
import pkgutil
import importlib
import chronix_bot.cogs as cogs_pkg
from chronix_bot.utils import persistence as persistence_utils
from chronix_bot.utils import db as db_utils
from chronix_bot.utils import logger as chronix_logger


try:
    # optional import, our health server uses aiohttp
    from chronix_bot.utils.health import start_health_server
except Exception:
    start_health_server = None


class ChronixBot(commands.Bot):
    def __init__(self, settings: Settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings

    async def close(self) -> None:
        # Graceful shutdown: close bot and then DB pool if initialized
        try:
            await super().close()
        finally:
            try:
                await db_utils.close_pool()
            except Exception:
                pass

    async def setup_hook(self) -> None:
        # Discover cogs
        names = []
        try:
            for finder, name, ispkg in pkgutil.iter_modules(cogs_pkg.__path__):
                names.append(name)
        except Exception as exc:
            print("Warning: failed to discover cogs:", exc)

        # Attempt dependency-aware loading: cogs may expose COG_DEPENDS = ["othercog"]
        deps_map = {}
        for name in names:
            full = f"chronix_bot.cogs.{name}"
            try:
                mod = importlib.import_module(full)
                deps = getattr(mod, "COG_DEPENDS", []) or []
                deps_map[name] = set(d.split(".")[-1] for d in deps)
            except Exception:
                deps_map[name] = set()

        remaining: Set[str] = set(names)
        loaded: Set[str] = set()

        # iterative resolver
        while remaining:
            progress = False
            for name in list(remaining):
                needed = deps_map.get(name, set())
                if needed.issubset(loaded):
                    full = f"chronix_bot.cogs.{name}"
                    try:
                        await self.load_extension(full)
                        print(f"Loaded extension: {full}")
                    except Exception as exc:
                        print(f"Warning: failed to load extension {full}:", exc)
                    loaded.add(name)
                    remaining.remove(name)
                    progress = True
            if not progress:
                # cyclic or unresolved dependencies - load the rest best-effort
                for name in list(remaining):
                    full = f"chronix_bot.cogs.{name}"
                    try:
                        await self.load_extension(full)
                        print(f"Loaded extension (best-effort): {full}")
                    except Exception as exc:
                        print(f"Warning: failed to load extension {full} on best-effort:", exc)
                    remaining.remove(name)
                break

        # Register a lightweight ping command if not present
        try:
            @self.tree.command(name="ping", description="Check bot latency")
            async def _ping(interaction: discord.Interaction):
                latency = round(self.latency * 1000)
                embed = discord.Embed(title="Pong!", description=f"Latency: {latency}ms")
                await interaction.response.send_message(embed=embed)
        except Exception:
            # ignore registration errors during setup
            pass

        # Sync to dev guild for faster iteration when configured
        dev_guild = getattr(self.settings, "DEV_GUILD_ID", None)
        if dev_guild:
            try:
                guild_obj = Object(id=int(dev_guild))
                await self.tree.sync(guild=guild_obj)
                print(f"Synced app commands to dev guild {dev_guild}")
            except Exception as e:
                print("Failed to sync app commands:", e)

        # Start optional health server if available
        try:
            if start_health_server is not None:
                host = os.getenv("HEALTH_HOST", "0.0.0.0")
                port = int(os.getenv("HEALTH_PORT", "8080"))
                # Start in background so setup_hook doesn't block
                self.loop.create_task(start_health_server(host=host, port=port))
        except Exception as e:
            print("Failed to start health server:", e)

        # Start automated log retention/prune task if enabled in settings
        try:
            if getattr(self.settings, "LOG_PRUNE_ENABLED", False):
                retention_days = int(getattr(self.settings, "LOG_RETENTION_DAYS", 30))
                interval_hours = int(getattr(self.settings, "LOG_PRUNE_INTERVAL_HOURS", 24))

                async def _prune_loop():
                    # initial delay to avoid hammering on startup
                    await self.loop.run_in_executor(None, lambda: None)
                    while True:
                        try:
                            # run prune synchronously in executor to avoid blocking loop
                            kept = await self.loop.run_in_executor(None, chronix_logger.prune_jsonl_archive, retention_days)
                            print(f"Log retention: kept {kept} entries (retention={retention_days}d)")
                        except Exception as e:
                            print("Log retention task failed:", e)
                        # sleep
                        await _aio.sleep(interval_hours * 60 * 60)

                import asyncio as _aio
                # create task using event loop
                self.loop.create_task(_prune_loop())
                print("Started automated log retention task (enabled)")
        except Exception as e:
            print("Failed to start log retention task:", e)


def create_bot(settings: Optional[Settings] = None) -> commands.Bot:
    """Create and return a configured ChronixBot instance."""
    if settings is None:
        settings = Settings()

    intents = discord.Intents.default()
    intents.message_content = True

    # dynamic per-guild prefix lookup using file-backed persistence
    def _prefix_callable(bot_instance, message):
        default = "chro "
        try:
            if message.guild is None:
                return default
            gid = int(message.guild.id)
            p = persistence_utils.get_guild_setting(gid, "prefix", default)
            return p
        except Exception:
            return default

    bot = ChronixBot(settings, command_prefix=_prefix_callable, intents=intents)

    # Global maintenance check: if per-guild maintenance mode is enabled, only owner may run commands
    async def _maintenance_check(ctx: commands.Context) -> bool:
        try:
            if ctx.guild is None:
                return True
            gid = int(ctx.guild.id)
            m = persistence_utils.get_guild_setting(gid, "maintenance", False)
            if m:
                owner = getattr(settings, "OWNER_ID", None)
                if owner is None:
                    return False
                return int(ctx.author.id) == int(owner)
            return True
        except Exception:
            return True

    bot.add_check(_maintenance_check)

    return bot
