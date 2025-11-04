"""Dashboard action consumer cog.

This owner-only cog polls the `data/dashboard_actions.json` file for actions
recorded by the local dashboard UI and applies them to the running bot.

Supported actions (from the dashboard):
- {op: "enable", cog: "name"}     -> will attempt to load `chronix_bot.cogs.name`
- {op: "disable", cog: "name"}    -> will attempt to unload the extension
- {op: "reload", cog: "name"}     -> reload if loaded, otherwise load
- {op: "instance.start/stop/restart"} -> recorded but not acted on unless
  env CHRONIX_ALLOW_SELF_RESTART=true (restart will exit the process)

Behavioral notes:
- Only the owner may run the explicit command to apply actions manually.
- The background loop will attempt to process pending actions every
  `CHRONIX_DASHBOARD_POLL_INTERVAL` seconds (default 6).
"""
from __future__ import annotations

import os
import asyncio
import traceback
from typing import Any, Dict, List

import discord
from discord.ext import commands, tasks

from chronix_bot.dashboard import worker as dashboard_worker


DEFAULT_POLL = int(os.environ.get("CHRONIX_DASHBOARD_POLL_INTERVAL", "6"))
ALLOW_SELF_RESTART = os.environ.get("CHRONIX_ALLOW_SELF_RESTART", "false").lower() in ("1", "true", "yes")


class DashboardConsumer(commands.Cog):
    """Background consumer that applies dashboard actions to the bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
    self._task = None
    # event used to wake the consumer loop for immediate processing
    self._consume_event = asyncio.Event()

    async def cog_load(self) -> None:  # called when cog is loaded in v2.x
        # start background loop
        self._task = self.bot.loop.create_task(self._consumer_loop())
        # expose a trigger on the bot so external RPC code can wake this consumer
        try:
            setattr(self.bot, '_dashboard_consumer_trigger', self.trigger_consume)
            # also expose a direct dispatcher so the RPC server can deliver actions
            setattr(self.bot, '_dashboard_consumer_dispatch', self._dispatch_actions)
        except Exception:
            pass

    async def cog_unload(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        try:
            if hasattr(self.bot, '_dashboard_consumer_trigger'):
                delattr(self.bot, '_dashboard_consumer_trigger')
        except Exception:
            pass
        try:
            if hasattr(self.bot, '_dashboard_consumer_dispatch'):
                delattr(self.bot, '_dashboard_consumer_dispatch')
        except Exception:
            pass

    async def _consumer_loop(self) -> None:
        await self.bot.wait_until_ready()
        while True:
            try:
                pending = dashboard_worker.read_pending_actions()
                if pending:
                    for act in pending:
                        try:
                            await self._handle_action(act)
                            dashboard_worker.mark_action_processed(act, {"status": "ok"})
                        except Exception as e:
                            dashboard_worker.mark_action_processed(act, {"status": "error", "error": str(e)})
                # wait until either the event is set (immediate trigger) or the normal poll interval expires
                try:
                    await asyncio.wait_for(self._consume_event.wait(), timeout=DEFAULT_POLL)
                    # clear the event if it was set
                    self._consume_event.clear()
                except asyncio.TimeoutError:
                    # timeout expired, loop will continue
                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                # swallow errors — this loop should be resilient
                traceback.print_exc()
                await asyncio.sleep(DEFAULT_POLL)

    async def _handle_action(self, action: Dict[str, Any]) -> None:
        op = action.get("op")
        # special trigger to force immediate consumption: process all pending
        if op == 'consume_now':
            pending = dashboard_worker.read_pending_actions()
            # process other pending actions (skip the consume_now marker itself)
            for act in [a for a in pending if a.get('op') != 'consume_now']:
                try:
                    await self._handle_action(act)
                    dashboard_worker.mark_action_processed(act, {"status": "ok"})
                except Exception as e:
                    dashboard_worker.mark_action_processed(act, {"status": "error", "error": str(e)})
            return
        # instance ops are recorded as op: "instance.start" etc
        if op and op.startswith("instance."):
            # do not perform start/stop by default — only log/store the intent
            # If explicitly enabled via env, allow process restart
            sub = op.split('.', 1)[1]
            if sub == "restart" and ALLOW_SELF_RESTART:
                # graceful shutdown then exit
                await self.bot.close()
                # prefer a hard exit to ensure supervisor restarts the container
                os._exit(0)
            # otherwise, nothing to do here
            return

        cog = action.get("cog")
        if not cog:
            return
        module = f"chronix_bot.cogs.{cog}"
        # attempt to load the config from dashboard files when relevant
        from chronix_bot.utils import dashboard as dashboard_utils
        # enable
        if op == "enable":
            if module in self.bot.extensions:
                return
            await self._safe_load(module)
        elif op == "disable":
            if module not in self.bot.extensions:
                return
            await self._safe_unload(module)
        elif op == "reload":
            if module in self.bot.extensions:
                await self._safe_reload(module)
            else:
                await self._safe_load(module)
        elif op == "hot_reload":
            # reload all loaded extensions (owner-only action from dashboard)
            failed = []
            for ext in list(self.bot.extensions.keys()):
                try:
                    self.bot.reload_extension(ext)
                except Exception:
                    failed.append(ext)
            if failed:
                raise RuntimeError(f"Some extensions failed to reload: {failed}")
        elif op == 'config':
            # load config and deliver to cog if it supports apply_dashboard_config
            cfg = dashboard_utils.get_cog_config(cog)
            # store in bot-level cache
            try:
                self.bot._dashboard_cog_configs = getattr(self.bot, '_dashboard_cog_configs', {})
                self.bot._dashboard_cog_configs[cog] = cfg
            except Exception:
                pass
            # attempt to find an instantiated Cog and call its hook
            try:
                # look for a cog instance whose module name includes the cog string
                for name, inst in list(self.bot.cogs.items()):
                    try:
                        mod = getattr(inst, '__module__', '')
                        if cog in mod or name.lower() == cog.lower():
                            if hasattr(inst, 'apply_dashboard_config'):
                                maybe = inst.apply_dashboard_config(cfg)
                                if hasattr(maybe, '__await__'):
                                    await maybe
                    except Exception:
                        continue
            except Exception:
                pass
            return
        elif op == 'action':
            # forward action to the cog instance if available
            action_name = action.get('action')
            payload = action.get('payload') or {}
            try:
                for name, inst in list(self.bot.cogs.items()):
                    try:
                        mod = getattr(inst, '__module__', '')
                        if cog in mod or name.lower() == cog.lower():
                            if hasattr(inst, 'handle_dashboard_action'):
                                maybe = inst.handle_dashboard_action(action_name, payload)
                                if hasattr(maybe, '__await__'):
                                    await maybe
                                break
                    except Exception:
                        continue
            except Exception:
                pass
            return

    async def _safe_load(self, module: str) -> None:
        try:
            await self.bot.load_extension(module)
        except Exception as e:
            # wrap and re-raise so the caller records error
            raise RuntimeError(f"load failed for {module}: {e}")

    async def _safe_unload(self, module: str) -> None:
        try:
            await self.bot.unload_extension(module)
        except Exception as e:
            raise RuntimeError(f"unload failed for {module}: {e}")

    async def _safe_reload(self, module: str) -> None:
        try:
            self.bot.reload_extension(module)
        except Exception:
            # reload_extension may raise; try load as fallback
            try:
                await self.bot.load_extension(module)
            except Exception as e:
                raise RuntimeError(f"reload/load fallback failed for {module}: {e}")

    # Manual admin trigger: owner-only command to force-consume pending actions
    @commands.is_owner()
    @commands.command(name="dashboard_consume")
    async def cmd_consume(self, ctx: commands.Context) -> None:
        """Manually consume and apply pending dashboard actions."""
        pending = dashboard_worker.read_pending_actions()
        if not pending:
            await ctx.send("No pending dashboard actions.")
            return
        await ctx.send(f"Processing {len(pending)} actions...")
        ok = 0
        fail = 0
        for act in pending:
            try:
                await self._handle_action(act)
                dashboard_worker.mark_action_processed(act, {"status": "ok"})
                ok += 1
            except Exception as e:
                dashboard_worker.mark_action_processed(act, {"status": "error", "error": str(e)})
                fail += 1
        await ctx.send(f"Done. OK: {ok}, Failed: {fail}")

    async def trigger_consume(self) -> None:
        """External trigger to wake the consumer loop and process pending actions quickly."""
        try:
            # set the event which the loop is waiting on
            self._consume_event.set()
        except Exception:
            pass

    async def _dispatch_actions(self, actions):
        """Dispatch a list of action dicts immediately and return a list of results.

        This method is intended to be called by the bot RPC server when the
        dashboard POSTs actions for immediate application.
        """
        results = []
        for act in actions or []:
            try:
                await self._handle_action(act)
                # mark as processed in the worker audit file
                try:
                    dashboard_worker.mark_action_processed(act, {"status": "ok"})
                except Exception:
                    pass
                results.append({"op": act.get('op'), "cog": act.get('cog'), "status": "ok"})
            except Exception as e:
                try:
                    dashboard_worker.mark_action_processed(act, {"status": "error", "error": str(e)})
                except Exception:
                    pass
                results.append({"op": act.get('op'), "cog": act.get('cog'), "status": "error", "error": str(e)})
        return results


async def setup(bot: commands.Bot):
    await bot.add_cog(DashboardConsumer(bot))
