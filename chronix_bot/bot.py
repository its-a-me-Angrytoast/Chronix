"""Bot factory for Chronix.

Creates and configures the commands.Bot instance and auto-loads the core cog.
"""
from typing import Optional, Set
import os
import time
import json
from pathlib import Path
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
# aiohttp used for small internal RPC endpoint
try:
    from aiohttp import web
except Exception:
    web = None


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
        # record start time for uptime calculations
        try:
            self._start_time = time.time()
        except Exception:
            self._start_time = None
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

        # Background stats writer for the dashboard (writes server_count to data/dashboard_stats.json)
        try:
            data_dir = Path(os.environ.get("CHRONIX_DATA_DIR", Path(__file__).parents[2] / "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            stats_file = data_dir / 'dashboard_stats.json'

            async def _stats_loop():
                # wait until the bot is ready and then periodically write telemetry
                await self.wait_until_ready()
                interval = int(os.getenv('CHRONIX_DASHBOARD_POLL_INTERVAL', '6'))
                import asyncio as _aio
                while True:
                    try:
                        guild_count = len(self.guilds) if getattr(self, 'guilds', None) is not None else 0
                        ext_count = len(getattr(self, 'extensions', {})) if getattr(self, 'extensions', None) is not None else len(getattr(self, 'extensions', {}))
                        # attempt to compute uptime
                        uptime = None
                        try:
                            if getattr(self, '_start_time', None):
                                uptime = int(time.time() - self._start_time)
                        except Exception:
                            uptime = None
                        payload = {
                            'server_count': guild_count,
                            'extensions': ext_count,
                            'uptime': uptime,
                            'ts': int(time.time()),
                            'pid': os.getpid()
                        }
                        # write the JSON file for the dashboard to read
                        stats_file.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
                    except Exception:
                        # best-effort; ignore failures
                        pass
                    await _aio.sleep(interval)

            self.loop.create_task(_stats_loop())
        except Exception as e:
            print('Failed to start dashboard stats writer:', e)

        # Optional simple RPC server to accept immediate apply requests from the dashboard.
        # This server is bound to localhost by default and accepts an X-API-Key header if configured.
        async def _start_rpc_server():
            if web is None:
                return
            try:
                rpc_host = os.getenv('CHRONIX_DASHBOARD_RPC_HOST', '127.0.0.1')
                rpc_port = int(os.getenv('CHRONIX_DASHBOARD_RPC_PORT', '9091'))
                api_key = os.environ.get('CHRONIX_DASHBOARD_API_KEY')

                app_rpc = web.Application()

                async def _consume_handler(req: web.Request):
                    # allow only localhost by default
                    peer = req.remote
                    local_hosts = ('127.0.0.1', '::1', 'localhost')
                    # API key check for non-local clients
                    if peer not in local_hosts and api_key:
                        key = req.headers.get('X-API-Key')
                        if not key or key != api_key:
                            return web.json_response({'status': 'unauthorized'}, status=401)
                    # if the bot exposes a consumer dispatcher, accept posted actions and dispatch them
                    try:
                        data = None
                        try:
                            data = await req.json()
                        except Exception:
                            data = None

                        actions = None
                        if isinstance(data, dict) and data.get('actions'):
                            actions = data.get('actions')
                        # If actions were provided, try to dispatch them immediately using the consumer dispatch hook
                        dispatch = getattr(self, '_dashboard_consumer_dispatch', None)
                        if actions and dispatch:
                            # dispatch may be coroutine
                            res = dispatch(actions)
                            if hasattr(res, '__await__'):
                                results = await res
                            else:
                                results = res
                            return web.json_response({'status': 'ok', 'results': results})

                        # No actions provided or no dispatcher available: fall back to simple trigger
                        trigger = getattr(self, '_dashboard_consumer_trigger', None)
                        if trigger:
                            res = trigger()
                            if hasattr(res, '__await__'):
                                # schedule trigger asynchronously
                                self.loop.create_task(res)
                        else:
                            # no consumer loaded yet — fallback: write a consume_now action file
                            data_dir = Path(os.environ.get('CHRONIX_DATA_DIR', Path(__file__).parents[2] / 'data'))
                            trig = data_dir / 'dashboard_trigger'
                            try:
                                trig.write_text(str(time.time()), encoding='utf-8')
                            except Exception:
                                pass
                        return web.json_response({'status': 'ok'})
                    except Exception:
                        return web.json_response({'status': 'error'}, status=500)

                app_rpc.router.add_post('/rpc/consume', _consume_handler)

                runner = web.AppRunner(app_rpc)
                await runner.setup()
                site = web.TCPSite(runner, rpc_host, rpc_port)
                await site.start()
                print(f"Started dashboard RPC server on {rpc_host}:{rpc_port}")
            except Exception as e:
                print('Failed to start dashboard RPC server:', e)

        try:
            # don't block setup_hook
            self.loop.create_task(_start_rpc_server())
        except Exception as e:
            print('Failed to schedule RPC server starter:', e)

        # Optionally open the dashboard in a browser on bot startup (local dev convenience)
        try:
            if os.getenv('CHRONIX_DASHBOARD_OPEN_BROWSER', 'false').lower() in ('1','true','yes'):
                import webbrowser
                host = os.getenv('CHRONIX_DASHBOARD_HOST', '127.0.0.1')
                port = int(os.getenv('CHRONIX_DASHBOARD_PORT', '8081'))
                url = f'http://{host}:{port}/'
                # open in a new tab without blocking
                try:
                    self.loop.call_soon_threadsafe(lambda: webbrowser.open_new_tab(url))
                except Exception:
                    # best-effort fallback
                    webbrowser.open_new_tab(url)
        except Exception:
            pass

        # Load existing per-cog configs and dispatch to cogs that implement apply_dashboard_config
        try:
            from chronix_bot.utils import dashboard as dashboard_utils
            self._dashboard_cog_configs = dashboard_utils.list_cog_configs()
            # deliver configs to cogs
            for cog_name, cfg in list(self._dashboard_cog_configs.items()):
                try:
                    for name, inst in list(self.cogs.items()):
                        mod = getattr(inst, '__module__', '')
                        if cog_name in mod or name.lower() == cog_name.lower():
                            if hasattr(inst, 'apply_dashboard_config'):
                                maybe = inst.apply_dashboard_config(cfg)
                                if hasattr(maybe, '__await__'):
                                    await maybe
                except Exception:
                    continue
        except Exception:
            # best-effort; don't block startup on config application
            pass

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
