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
                        
                        is_maintenance = os.getenv('CHRONIX_DASHBOARD_MAINTENANCE', 'false').lower() in ('true', '1', 'yes')
                        payload = {
                            'server_count': guild_count,
                            'extensions': ext_count,
                            'uptime': uptime,
                            'ts': int(time.time()),
                            'pid': os.getpid(),
                            'maintenance_mode': is_maintenance
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
            if os.getenv('CHRONIX_DASHBOARD_STANDALONE', 'false').lower() in ('true', '1', 'yes'):
                print("Internal dashboard server disabled (CHRONIX_DASHBOARD_STANDALONE is set).")
                return

            try:
                import uvicorn
                from fastapi import FastAPI, Request, Response
                from fastapi.responses import JSONResponse, FileResponse
                from fastapi.staticfiles import StaticFiles
                from fastapi.middleware.cors import CORSMiddleware
            except ImportError:
                print("FastAPI or Uvicorn not installed. Dashboard RPC/hosting disabled.")
                return

            try:
                rpc_host = os.getenv('CHRONIX_DASHBOARD_RPC_HOST', '127.0.0.1')
                rpc_port = int(os.getenv('CHRONIX_DASHBOARD_RPC_PORT', '9091'))
                api_key = os.environ.get('CHRONIX_DASHBOARD_API_KEY')

                app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

                # Basic CORS setup
                app.add_middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_credentials=True,
                    allow_methods=["*"],
                    allow_headers=["*"],
                )

                @app.post('/rpc/consume')
                async def _consume_handler(request: Request):
                    # Security checks
                    client_host = request.client.host if request.client else "unknown"
                    local_hosts = ('127.0.0.1', '::1', 'localhost')
                    if client_host not in local_hosts and api_key:
                        key = request.headers.get('X-API-Key')
                        if not key or key != api_key:
                            return JSONResponse({'status': 'unauthorized'}, status_code=401)

                    try:
                        data = await request.json()
                    except Exception:
                        data = None

                    actions = None
                    if isinstance(data, dict) and data.get('actions'):
                        actions = data.get('actions')

                    # Check for maintenance mode
                    if os.getenv('CHRONIX_DASHBOARD_MAINTENANCE', 'false').lower() in ('true', '1', 'yes'):
                        if actions:
                            return JSONResponse({
                                'status': 'error',
                                'message': 'Maintenance mode active. Changes are not saved.'
                            }, status_code=503)

                    # Dispatch actions
                    dispatch = getattr(self, '_dashboard_consumer_dispatch', None)
                    if actions and dispatch:
                        try:
                            res = dispatch(actions)
                            if hasattr(res, '__await__'):
                                results = await res
                            else:
                                results = res
                            return JSONResponse({'status': 'ok', 'results': results})
                        except Exception:
                            return JSONResponse({'status': 'error'}, status_code=500)

                    # Fallback trigger
                    trigger = getattr(self, '_dashboard_consumer_trigger', None)
                    if trigger:
                        res = trigger()
                        if hasattr(res, '__await__'):
                            self.loop.create_task(res)
                    else:
                        data_dir = Path(os.environ.get('CHRONIX_DATA_DIR', Path(__file__).parents[2] / 'data'))
                        try:
                            (data_dir / 'dashboard_trigger').write_text(str(time.time()), encoding='utf-8')
                        except Exception:
                            pass
                    return JSONResponse({'status': 'ok'})

                @app.get('/api/stats')
                async def _get_stats():
                    data_dir = Path(os.environ.get('CHRONIX_DATA_DIR', Path(__file__).parents[2] / 'data'))
                    stats_file = data_dir / 'dashboard_stats.json'
                    if stats_file.exists():
                        try:
                            content = json.loads(stats_file.read_text(encoding='utf-8'))
                            # Add explicit ping if not in file (calculated here or passed from bot)
                            # For now, just return what's in the file. The bot loop writes uptime/server_count.
                            # The ping command in bot.py calculates latency but doesn't write it to the file.
                            # We can rely on the client to fetch latency or just show uptime/servers.
                            return JSONResponse(content)
                        except Exception:
                            pass
                    return JSONResponse({'server_count': 0, 'uptime': 0, 'extensions': 0, 'maintenance_mode': False})

                # Serve Dashboard Static Files
                dashboard_dist = Path(os.environ.get('CHRONIX_DASHBOARD_BUILD_DIR', Path(__file__).parents[2] / 'dashboard' / 'dist'))
                if dashboard_dist.exists() and dashboard_dist.is_dir():
                    # Mount assets
                    assets_path = dashboard_dist / 'assets'
                    if assets_path.exists():
                        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

                    # Serve root files
                    for root_file in ['favicon.ico', 'manifest.json', 'robots.txt', 'logo192.png', 'logo512.png']:
                         if (dashboard_dist / root_file).exists():
                             # capture variable in default arg
                             @app.get(f"/{root_file}")
                             async def _serve_root(rf=root_file): 
                                 return FileResponse(dashboard_dist / rf)

                    # SPA Catch-all (serves index.html for any other route)
                    @app.get("/{full_path:path}")
                    async def _serve_spa(full_path: str):
                        return FileResponse(dashboard_dist / 'index.html')

                    print(f"Serving dashboard from {dashboard_dist}")
                else:
                    print(f"Dashboard build not found at {dashboard_dist}. Run 'npm run build' in dashboard/ directory.")

                # Start Uvicorn
                config = uvicorn.Config(app, host=rpc_host, port=rpc_port, log_level="info")
                server = uvicorn.Server(config)
                # IMPORTANT: Prevent uvicorn from overwriting signal handlers (Ctrl+C), let discord.py handle it
                server.install_signal_handlers = lambda: None
                
                print(f"Started dashboard FastAPI server on {rpc_host}:{rpc_port}")
                await server.serve()
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
