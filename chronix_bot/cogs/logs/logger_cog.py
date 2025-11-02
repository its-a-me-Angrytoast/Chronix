"""Logging cog: listens for message edits/deletes, joins/leaves, bans, and guild updates.

Creates log channels via a `chro create-logs` command and writes structured
entries to those channels and the async logger queue in `chronix_bot.utils.logger`.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import logger as chronix_logger
from chronix_bot.utils import helpers
from chronix_bot.utils import persistence as persistence_utils
from pathlib import Path
import time
import json
import os
try:
    import aiohttp
except Exception:
    aiohttp = None


DATA_PATH = Path.cwd() / "data"
LOG_CONFIG_FILE = DATA_PATH / "log_configs.json"


def _load_configs() -> dict:
    if not LOG_CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(LOG_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_configs(cfg: dict) -> None:
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    LOG_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


class LoggerCog(commands.Cog):
    """Cog that routes important server events into configured log channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._configs = _load_configs()  # guild_id -> {"moderation": id, "messages": id, ...}

    # ---- helpers
    def _get_channel(self, guild: discord.Guild, kind: str) -> Optional[discord.TextChannel]:
        cfg = self._configs.get(str(guild.id), {})
        cid = cfg.get(kind)
        if not cid:
            return None
        return guild.get_channel(int(cid))

    def _log_queue(self, payload: object) -> None:
        try:
            chronix_logger.enqueue_log(payload)
        except Exception:
            pass
        # forward to configured webhook if present
        try:
            gid = None
            if isinstance(payload, dict):
                gid = payload.get("guild") or payload.get("guild_id")
            if gid:
                cfg = self._configs.get(str(gid), {})
                url = cfg.get("webhook")
                if url and aiohttp is not None:
                    # schedule fire-and-forget forward
                    try:
                        self.bot.loop.create_task(self._forward_to_webhook(url, payload))
                    except Exception:
                        pass
        except Exception:
            pass
        # send to developer debug channel if configured
        try:
            dev_ch = os.getenv("DEV_LOG_CHANNEL_ID")
            if dev_ch:
                try:
                    cid = int(dev_ch)
                    # best-effort: find the channel across bot's guilds
                    ch = None
                    for g in self.bot.guilds:
                        ch = g.get_channel(cid)
                        if ch:
                            break
                    if ch:
                        # format a compact message
                        try:
                            text = json.dumps(payload, default=str) if isinstance(payload, dict) else str(payload)
                        except Exception:
                            text = str(payload)
                        # avoid long messages
                        if len(text) > 1900:
                            text = text[:1900] + "..."
                        self.bot.loop.create_task(ch.send(f"[DEV LOG] {text}"))
                except Exception:
                    pass
        except Exception:
            pass

    async def _forward_to_webhook(self, url: str, payload: object) -> None:
        if aiohttp is None:
            return
        try:
            async with aiohttp.ClientSession() as sess:
                await sess.post(url, json=payload, timeout=10)
        except Exception:
            # don't raise; best-effort
            return

    def _send_to_channel(self, guild: discord.Guild, kind: str, embed: discord.Embed):
        ch = self._get_channel(guild, kind)
        if ch is None:
            return
        # fire-and-forget send
        try:
            self.bot.loop.create_task(ch.send(embed=embed))
        except Exception:
            pass

    # ---- commands
    @commands.command(name="create-logs")
    @commands.has_permissions(manage_guild=True)
    async def create_logs(self, ctx: commands.Context):
        """Create standardized log channels for this guild (moderation, messages, server, errors)."""
        guild = ctx.guild
        if guild is None:
            await ctx.send("This command must be used in a server.")
            return
        names = {
            "moderation": "moderation-logs",
            "messages": "message-logs",
            "server": "server-logs",
            "errors": "error-logs",
        }
        created = {}
        for key, name in names.items():
            # try to find existing channel
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch is None:
                try:
                    ch = await guild.create_text_channel(name, reason="Chronix log channel creation")
                except Exception:
                    ch = None
            if ch:
                created[key] = ch.id

        if str(guild.id) not in self._configs:
            self._configs[str(guild.id)] = {}
        self._configs[str(guild.id)].update(created)
        _save_configs(self._configs)

        await ctx.send(embed=helpers.make_embed("Log channels created", f"Created/registered channels: {', '.join(created.keys())}"))
        self._log_queue({"type": "create_logs", "guild": guild.id, "created": created, "by": ctx.author.id})

    @commands.command(name="create-logs-emoji")
    @commands.has_permissions(manage_guild=True)
    async def create_logs_emoji(self, ctx: commands.Context):
        """Create standardized emoji-prefixed log channels with sane permissions.

        Channels will be created with an emoji prefix for readability, and the
        default @everyone role will be denied send_messages so logs are write-only.
        Roles with Manage Guild will be allowed to view and send in those channels.
        """
        guild = ctx.guild
        if guild is None:
            await ctx.send("This command must be used in a server.")
            return

        names = {
            "moderation": ("🔒", "moderation-logs"),
            "messages": ("💬", "message-logs"),
            "server": ("🧭", "server-logs"),
            "errors": ("❗", "error-logs"),
        }
        created = {}
        # build staff roles set
        staff_roles = [r for r in guild.roles if r.permissions.manage_guild]
        for key, (emoji, base) in names.items():
            chan_name = f"{emoji} | {base}"
            ch = discord.utils.get(guild.text_channels, name=chan_name)
            if ch is None:
                # prepare overwrites: deny send for @everyone, allow for staff
                overwrites = {guild.default_role: discord.PermissionOverwrite(send_messages=False, view_channel=True)}
                for r in staff_roles:
                    overwrites[r] = discord.PermissionOverwrite(send_messages=True, view_channel=True)
                try:
                    ch = await guild.create_text_channel(chan_name, overwrites=overwrites, reason="Chronix emoji-prefixed log channel creation")
                except Exception:
                    ch = None
            if ch:
                created[key] = ch.id

        if str(guild.id) not in self._configs:
            self._configs[str(guild.id)] = {}
        self._configs[str(guild.id)].update(created)
        _save_configs(self._configs)

        await ctx.send(embed=helpers.make_embed("Emoji log channels created", f"Created/registered channels: {', '.join(created.keys())}"))
        self._log_queue({"type": "create_logs_emoji", "guild": guild.id, "created": created, "by": ctx.author.id})

    @commands.command(name="logs")
    @commands.has_permissions(manage_guild=True)
    async def logs(self, ctx: commands.Context, subcommand: Optional[str] = None):
        """Logs command group. Usage: chro logs view"""
        if subcommand is None or subcommand.lower() != "view":
            await ctx.send("Usage: chro logs view")
            return
        guild = ctx.guild
        if guild is None:
            await ctx.send("This command must be used in a server.")
            return
        cfg = self._configs.get(str(guild.id), {})
        if not cfg:
            await ctx.send("No log channels configured for this guild.")
            return
        lines = []
        for k, v in cfg.items():
            ch = guild.get_channel(int(v)) if v else None
            lines.append(f"{k}: {ch.mention if ch else 'Not found / unset'}")
        await ctx.send("\n".join(lines))

    @commands.command(name="export-logs")
    @commands.has_permissions(manage_guild=True)
    async def export_logs(self, ctx: commands.Context):
        """Export structured logs (JSONL) to a timestamped file and attach it."""
        data_dir = Path.cwd() / "data"
        archive = data_dir / "logs.jsonl"
        if not archive.exists():
            await ctx.send("No logs available to export.")
            return
        # create export snapshot
        ts = int(time.time())
        out = data_dir / f"logs_export_{ctx.guild.id}_{ts}.jsonl"
        try:
            # copy file (best-effort)
            with archive.open("r", encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
                for line in src:
                    dst.write(line)
            await ctx.send("Logs exported:", file=discord.File(fp=str(out), filename=out.name))
        except Exception as e:
            await ctx.send(f"Export failed: {e}")

    @commands.command(name="prune-logs")
    @commands.has_permissions(manage_guild=True)
    async def prune_logs(self, ctx: commands.Context, days: int = 30):
        """Prune archived logs older than `days` days from the JSONL archive.

        This operates on `data/logs.jsonl` and rewrites a filtered file.
        """
        try:
            kept = chronix_logger.prune_jsonl_archive(days=days)
            await ctx.send(f"Pruned logs; kept {kept} entries.")
        except Exception as e:
            await ctx.send(f"Prune failed: {e}")

    @commands.command(name="logs-search")
    @commands.has_permissions(manage_guild=True)
    async def logs_search(self, ctx: commands.Context, *, query: str):
        """Search logs.jsonl for simple filters: type:xyz user:123 guild:456 limit:N

        Examples:
        chro logs-search type:crate_open user:123 limit:20
        """
        data_dir = Path.cwd() / "data"
        archive = data_dir / "logs.jsonl"
        if not archive.exists():
            await ctx.send("No logs archive found.")
            return
        # parse simple tokens
        tokens = query.split()
        filters = {}
        limit = 50
        for t in tokens:
            if ":" in t:
                k, v = t.split(":", 1)
                if k == "limit":
                    try:
                        limit = int(v)
                    except Exception:
                        pass
                else:
                    filters[k] = v

        results = []
        try:
            with archive.open("r", encoding="utf-8") as f:
                for line in f:
                    if len(results) >= limit:
                        break
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    ok = True
                    for k, v in filters.items():
                        if k == "user":
                            if str(obj.get("user_id") or obj.get("author") or obj.get("target")) != str(v):
                                ok = False
                                break
                        elif k == "type":
                            if str(obj.get("type") or obj.get("event")) != str(v):
                                ok = False
                                break
                        elif k == "guild":
                            if str(obj.get("guild") or obj.get("guild_id")) != str(v):
                                ok = False
                                break
                    if ok:
                        results.append(obj)
            if not results:
                await ctx.send("No matching log entries found.")
                return
            lines = []
            for r in results[:20]:
                ts = r.get("ts")
                tstr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "?"
                lines.append(f"[{tstr}] {r.get('type') or r.get('event')} — {r.get('user_id') or r.get('target') or ''} — {r}")
            await ctx.send(embed=helpers.make_embed("Log Search Results", "\n".join(lines[:20])))
        except Exception as e:
            await ctx.send(f"Search failed: {e}")

    @commands.command(name="logs-view-ui")
    @commands.has_permissions(manage_guild=True)
    async def logs_view_ui(self, ctx: commands.Context, *, query: str):
        """Search logs and open a paginated UI to browse results.

        Usage: chro logs-view-ui type:crate_open user:123 limit:100
        """
        data_dir = Path.cwd() / "data"
        archive = data_dir / "logs.jsonl"
        if not archive.exists():
            await ctx.send("No logs archive found.")
            return

        # reuse filter parsing from logs_search
        tokens = query.split()
        filters = {}
        limit = 200
        for t in tokens:
            if ":" in t:
                k, v = t.split(":", 1)
                if k == "limit":
                    try:
                        limit = int(v)
                    except Exception:
                        pass
                else:
                    filters[k] = v

        results = []
        try:
            with archive.open("r", encoding="utf-8") as f:
                for line in f:
                    if len(results) >= limit:
                        break
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    ok = True
                    for k, v in filters.items():
                        if k == "user":
                            if str(obj.get("user_id") or obj.get("author") or obj.get("target")) != str(v):
                                ok = False
                                break
                        elif k == "type":
                            if str(obj.get("type") or obj.get("event")) != str(v):
                                ok = False
                                break
                        elif k == "guild":
                            if str(obj.get("guild") or obj.get("guild_id")) != str(v):
                                ok = False
                                break
                    if ok:
                        results.append(obj)
        except Exception as e:
            await ctx.send(f"Search failed: {e}")
            return

        if not results:
            await ctx.send("No matching log entries found.")
            return

        # build simple pagination using discord.ui.View
        from discord.ui import View, button

        page_size = 6
        pages = [results[i : i + page_size] for i in range(0, len(results), page_size)]

        class _Pager(View):
            def __init__(self, pages):
                super().__init__(timeout=300)
                self.pages = pages
                self.idx = 0

            async def _render(self):
                page = self.pages[self.idx]
                lines = []
                for r in page:
                    ts = r.get("ts")
                    tstr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "?"
                    lines.append(f"[{tstr}] {r.get('type') or r.get('event')} — {r.get('user_id') or r.get('target') or ''} — {r}")
                embed = helpers.make_embed(f"Log Results ({self.idx+1}/{len(self.pages)})", "\n".join(lines))
                return embed

            @button(label="Prev", style=discord.ButtonStyle.secondary)
            async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.idx > 0:
                    self.idx -= 1
                    await interaction.response.edit_message(embed=await self._render(), view=self)
                else:
                    await interaction.response.defer()

            @button(label="Next", style=discord.ButtonStyle.primary)
            async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.idx < len(self.pages) - 1:
                    self.idx += 1
                    await interaction.response.edit_message(embed=await self._render(), view=self)
                else:
                    await interaction.response.defer()

        view = _Pager(pages)
        embed = await view._render()
        await ctx.send(embed=embed, view=view)

    # ---- event listeners
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        guild = message.guild
        if not guild:
            return
        desc = f"Message deleted in {message.channel.mention} by {message.author.mention}\nContent: {message.content!r}"
        embed = helpers.make_embed("Message Deleted", desc)
        self._send_to_channel(guild, "messages", embed)
        self._log_queue({"type": "message_delete", "guild": guild.id, "author": message.author.id, "channel": message.channel.id, "content": message.content})

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return
        guild = before.guild
        if not guild:
            return
        if before.content == after.content:
            return
        desc = (
            f"Message edited in {before.channel.mention} by {before.author.mention}\n"
            f"Before: {before.content!r}\nAfter: {after.content!r}"
        )
        embed = helpers.make_embed("Message Edited", desc)
        self._send_to_channel(guild, "messages", embed)
        self._log_queue({"type": "message_edit", "guild": guild.id, "author": before.author.id, "channel": before.channel.id, "before": before.content, "after": after.content})

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        embed = helpers.make_embed("Member Joined", f"{member.mention} joined the server.")
        self._send_to_channel(guild, "server", embed)
        self._log_queue({"type": "member_join", "guild": guild.id, "user": member.id})

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        embed = helpers.make_embed("Member Left", f"{member.mention} left or was removed.")
        self._send_to_channel(guild, "server", embed)
        self._log_queue({"type": "member_remove", "guild": guild.id, "user": member.id})

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        # Try to augment with audit log info (who performed the ban)
        actor = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if getattr(entry.target, "id", None) == user.id:
                    actor = entry.user
                    break
        except Exception:
            actor = None

        desc = f"{user} was banned from the server."
        if actor:
            desc += f" Action by: {actor}"
        embed = helpers.make_embed("Member Banned", desc)
        self._send_to_channel(guild, "moderation", embed)
        self._log_queue({"type": "member_ban", "guild": guild.id, "user": user.id, "by": getattr(actor, "id", None)})

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        desc = "Guild updated."
        embed = helpers.make_embed("Guild Updated", desc)
        self._send_to_channel(after, "server", embed)
        self._log_queue({"type": "guild_update", "guild": after.id})

    @commands.Cog.listener()
    async def on_error(self, event_method: str, *args, **kwargs):
        # discord.py calls this for unhandled errors; capture and log
        tb = traceback.format_exc()
        # Best-effort: try to write to all configured error channels
        for gid, cfg in self._configs.items():
            try:
                guild = self.bot.get_guild(int(gid))
                if not guild:
                    continue
                ch_id = cfg.get("errors")
                if not ch_id:
                    continue
                ch = guild.get_channel(int(ch_id))
                if ch:
                    desc = "Event: {}\n```{}\n```".format(event_method, tb[:1900])
                    embed = helpers.make_embed("Unhandled Error", desc)
                    self.bot.loop.create_task(ch.send(embed=embed))
            except Exception:
                pass
        # also enqueue to async writer
        self._log_queue({"type": "unhandled_error", "event": event_method, "traceback": tb})


async def setup(bot: commands.Bot):
    cog = LoggerCog(bot)
    await bot.add_cog(cog)

    # Register slash equivalents and viewing/toggling commands on the app command tree
    try:
        @bot.tree.command(name="create-logs", description="Create standard log channels for this guild")
        async def _create_logs(interaction: discord.Interaction):
            await interaction.response.defer()
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            # reuse cog logic: create channels and persist
            names = {
                "moderation": "moderation-logs",
                "messages": "message-logs",
                "server": "server-logs",
                "errors": "error-logs",
            }
            created = {}
            for key, name in names.items():
                ch = discord.utils.get(guild.text_channels, name=name)
                if ch is None:
                    try:
                        ch = await guild.create_text_channel(name, reason="Chronix log channel creation")
                    except Exception:
                        ch = None
                if ch:
                    created[key] = ch.id

            if str(guild.id) not in cog._configs:
                cog._configs[str(guild.id)] = {}
            cog._configs[str(guild.id)].update(created)
            _save_configs(cog._configs)

            await interaction.followup.send(f"Created/registered channels: {', '.join(created.keys())}")
            cog._log_queue({"type": "create_logs", "guild": guild.id, "created": created, "by": interaction.user.id})

        @bot.tree.command(name="create-logs-emoji", description="Create emoji-prefixed log channels for this guild")
        async def _create_logs_emoji(interaction: discord.Interaction):
            await interaction.response.defer()
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            names = {
                "moderation": ("🔒", "moderation-logs"),
                "messages": ("💬", "message-logs"),
                "server": ("🧭", "server-logs"),
                "errors": ("❗", "error-logs"),
            }
            created = {}
            staff_roles = [r for r in guild.roles if r.permissions.manage_guild]
            for key, (emoji, base) in names.items():
                chan_name = f"{emoji} | {base}"
                ch = discord.utils.get(guild.text_channels, name=chan_name)
                if ch is None:
                    overwrites = {guild.default_role: discord.PermissionOverwrite(send_messages=False, view_channel=True)}
                    for r in staff_roles:
                        overwrites[r] = discord.PermissionOverwrite(send_messages=True, view_channel=True)
                    try:
                        ch = await guild.create_text_channel(chan_name, overwrites=overwrites, reason="Chronix emoji-prefixed log channel creation")
                    except Exception:
                        ch = None
                if ch:
                    created[key] = ch.id

            if str(guild.id) not in cog._configs:
                cog._configs[str(guild.id)] = {}
            cog._configs[str(guild.id)].update(created)
            _save_configs(cog._configs)

            await interaction.followup.send(f"Created/registered channels: {', '.join(created.keys())}")
            cog._log_queue({"type": "create_logs_emoji", "guild": guild.id, "created": created, "by": interaction.user.id})

        @bot.tree.command(name="logs-view", description="View configured log channels for this guild")
        async def _logs_view(interaction: discord.Interaction):
            await interaction.response.defer()
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            cfg = cog._configs.get(str(guild.id), {})
            if not cfg:
                await interaction.followup.send("No log channels configured for this guild.", ephemeral=True)
                return
            lines = []
            for k, v in cfg.items():
                ch = guild.get_channel(int(v)) if v else None
                lines.append(f"{k}: {ch.mention if ch else 'Not found / unset'}")
            await interaction.followup.send("\n".join(lines), ephemeral=True)

        @bot.tree.command(name="logs-toggle", description="Enable or disable a log category for this guild")
        async def _logs_toggle(interaction: discord.Interaction, category: str, state: str):
            await interaction.response.defer()
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            category = category.lower()
            if category not in ("moderation", "messages", "server", "errors"):
                await interaction.followup.send("Unknown category. Choose from moderation, messages, server, errors.", ephemeral=True)
                return
            state = state.lower()
            if state not in ("on", "off"):
                await interaction.followup.send("State must be 'on' or 'off'.", ephemeral=True)
                return
            cfg = cog._configs.setdefault(str(guild.id), {})
            if state == "off":
                cfg.pop(category, None)
                _save_configs(cog._configs)
                await interaction.followup.send(f"Disabled {category} logs.", ephemeral=True)
                cog._log_queue({"type": "logs_toggle", "guild": guild.id, "category": category, "state": "off", "by": interaction.user.id})
                return
            # turning on: must have an existing channel in guild named <category>-logs
            name_map = {"moderation": "moderation-logs", "messages": "message-logs", "server": "server-logs", "errors": "error-logs"}
            ch = discord.utils.get(guild.text_channels, name=name_map[category])
            if ch is None:
                # create if missing
                try:
                    ch = await guild.create_text_channel(name_map[category], reason="Chronix log channel creation via toggle")
                except Exception:
                    ch = None
            if ch:
                cfg[category] = ch.id
                _save_configs(cog._configs)
                await interaction.followup.send(f"Enabled {category} logs to {ch.mention}", ephemeral=True)
                cog._log_queue({"type": "logs_toggle", "guild": guild.id, "category": category, "state": "on", "channel": ch.id, "by": interaction.user.id})
            else:
                await interaction.followup.send(f"Failed to create or find channel for {category}", ephemeral=True)
    except Exception:
        # app command registration may fail in some environments; ignore
        pass

    # Add admin helper to set per-guild rare-drop channel used by crates
    @commands.command(name="set_rare_drop")
    @commands.has_permissions(manage_guild=True)
    async def set_rare_drop(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Configure the channel to post rare crate drop announcements. Use no args to clear."""
        try:
            gid = ctx.guild.id
            if channel is None:
                persistence_utils.set_guild_setting(gid, "rare_drop_channel", None)
                await ctx.send("Cleared rare-drop announcement channel for this guild.")
                return
            persistence_utils.set_guild_setting(gid, "rare_drop_channel", int(channel.id))
            await ctx.send(f"Set rare-drop announcements to {channel.mention}")
        except Exception as e:
            await ctx.send(f"Failed to set rare-drop channel: {e}")

    @commands.command(name="set_log_webhook")
    @commands.has_permissions(manage_guild=True)
    async def set_log_webhook(self, ctx: commands.Context, webhook_url: Optional[str] = None):
        """Configure an outgoing webhook URL to forward structured logs (POST JSON)."""
        try:
            gid = ctx.guild.id
            if webhook_url is None:
                # clear
                cfg = self._configs.get(str(gid), {})
                cfg.pop("webhook", None)
                _save_configs(self._configs)
                await ctx.send("Cleared log webhook for this guild.")
                return
            # basic validation
            if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
                await ctx.send("Provide a valid http(s) URL.")
                return
            if str(gid) not in self._configs:
                self._configs[str(gid)] = {}
            self._configs[str(gid)]["webhook"] = webhook_url
            _save_configs(self._configs)
            await ctx.send("Log webhook configured (best-effort forwarding enabled).")
        except Exception as e:
            await ctx.send(f"Failed to set webhook: {e}")
