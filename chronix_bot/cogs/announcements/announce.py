"""Announcement cog: create, preview, list, delete, and scheduler for posting announcements.

This cog uses `chronix_bot.utils.announcements` for persistence (file-backed by default).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import announcements as ann_utils
from chronix_bot.config import Settings

logger = logging.getLogger("chronix.announce")


class AnnounceCog(commands.Cog):
    """Cog to create and schedule announcements."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._scheduler_task = self.bot.loop.create_task(self._scheduler_loop())

    def cog_unload(self) -> None:
        if not self._scheduler_task.cancelled():
            self._scheduler_task.cancel()

    async def _post_announcement(self, record: dict) -> bool:
        guild = self.bot.get_guild(int(record.get("guild_id")))
        if not guild:
            return False
        try:
            channel = guild.get_channel(int(record.get("channel_id")))
            if channel is None:
                # try fetch
                channel = await self.bot.fetch_channel(int(record.get("channel_id")))
        except Exception:
            return False

        payload = record.get("payload", {}) or {}
        title = payload.get("title")
        description = payload.get("description")
        image = payload.get("image")
        embed = discord.Embed(title=title or "Announcement", description=description or "", color=0x2F3136, timestamp=datetime.now(timezone.utc))
        if image:
            embed.set_image(url=image)

        try:
            await channel.send(embed=embed)
            return True
        except Exception:
            return False

    async def _scheduler_loop(self):
        # Batch-run every 30 seconds
        await self.bot.wait_until_ready()
        while True:
            try:
                now = datetime.now(timezone.utc)
                due = await ann_utils.list_due(now=now, limit=25)
                if due:
                    for record in due:
                        ann_id = record.get("id")
                        try:
                            ok = await self._post_announcement(record)
                            if not ok:
                                # exponential backoff attempt
                                await ann_utils.increment_failure(ann_id)
                                # check failure_count
                                fc = int(record.get("failure_count", 0)) + 1
                                if fc > 3:
                                    logger.warning("Disabling announcement %s after %s failures", ann_id, fc)
                                    await ann_utils.update_announcement(ann_id, enabled=False)
                                else:
                                    # wait short and retry once
                                    await asyncio.sleep(2 ** fc)
                                    ok = await self._post_announcement(record)
                                    if ok:
                                        # reset failure_count and schedule next
                                        next_at = ann_utils._compute_next_from_repeat(record.get("repeat"), base=now)
                                        await ann_utils.mark_posted(ann_id, next_scheduled_at=next_at)
                            else:
                                # success path: schedule next or disable
                                next_at = ann_utils._compute_next_from_repeat(record.get("repeat"), base=now)
                                await ann_utils.mark_posted(ann_id, next_scheduled_at=next_at)
                        except Exception:
                            logger.exception("Error while posting announcement %s", ann_id)
                            await ann_utils.increment_failure(ann_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Announcement scheduler unexpected error")
                await asyncio.sleep(5)

    @commands.hybrid_group(name="announce", with_app_command=True)
    @commands.has_permissions(manage_guild=True)
    async def announce(self, ctx: commands.Context):
        """Announcement commands group (admin-only)."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use subcommands: create/preview/list/delete")

    @announce.command(name="create")
    async def create(self, ctx: commands.Context, channel: discord.TextChannel, when: str, *, content: str):
        """Create an announcement.

        when: ISO datetime or relative like `in 10m` or `in 2h`.
        content: markdown text for description. Optionally put `| title` after a line to set title.
        """
        # parse when
        scheduled_at = None
        now = datetime.now(timezone.utc)
        if when.startswith("in "):
            tok = when.split(" ", 1)[1]
            if tok.endswith("m"):
                try:
                    mins = int(tok[:-1])
                    scheduled_at = (now + timedelta(minutes=mins)).isoformat()
                except Exception:
                    scheduled_at = now.isoformat()
            elif tok.endswith("h"):
                try:
                    hrs = int(tok[:-1])
                    scheduled_at = (now + timedelta(hours=hrs)).isoformat()
                except Exception:
                    scheduled_at = now.isoformat()
            else:
                # try minutes
                try:
                    mins = int(tok)
                    scheduled_at = (now + timedelta(minutes=mins)).isoformat()
                except Exception:
                    scheduled_at = now.isoformat()
        else:
            # try ISO
            try:
                dt = datetime.fromisoformat(when)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                scheduled_at = dt.isoformat()
            except Exception:
                scheduled_at = now.isoformat()

        # allow title separator
        title = None
        description = content
        if "|" in content:
            parts = content.split("|", 1)
            title = parts[0].strip()
            description = parts[1].strip()

        payload = {"title": title or "Announcement", "description": description}
        record = await ann_utils.create_announcement(ctx.guild.id, channel.id, ctx.author.id, payload, scheduled_at=scheduled_at)
        await ctx.send(f"Announcement scheduled (id: {record.get('id')}).")

    @announce.command(name="preview")
    async def preview(self, ctx: commands.Context, *, content: str):
        """Preview an announcement embed from content (use `|` to separate title and body)."""
        title = None
        description = content
        if "|" in content:
            parts = content.split("|", 1)
            title = parts[0].strip()
            description = parts[1].strip()
        embed = discord.Embed(title=title or "Announcement", description=description or "", color=0x2F3136)
        await ctx.send(embed=embed)

    @announce.group(name="template", invoke_without_command=True)
    async def template(self, ctx: commands.Context):
        """Manage announcement templates."""
        await ctx.send("Use subcommands: create/list/delete/preview")

    @template.command(name="create")
    async def template_create(self, ctx: commands.Context, name: str, *, content: str):
        """Create a named template. Use `|` to separate title and body."""
        title = None
        description = content
        if "|" in content:
            parts = content.split("|", 1)
            title = parts[0].strip()
            description = parts[1].strip()
        payload = {"title": title or "Announcement", "description": description}
        rec = await ann_utils.create_template(name, payload)
        await ctx.send(f"Template `{name}` created.")

    @template.command(name="list")
    async def template_list(self, ctx: commands.Context):
        data = await ann_utils.list_templates()
        if not data:
            await ctx.send("No templates available.")
            return
        lines = [f"`{k}` - created: {v.get('created_at') or 'unknown'}" for k, v in data.items()]
        await ctx.send("Templates:\n" + "\n".join(lines[:50]))

    @template.command(name="delete")
    async def template_delete(self, ctx: commands.Context, name: str):
        ok = await ann_utils.delete_template(name)
        if ok:
            await ctx.send(f"Deleted template `{name}`.")
        else:
            await ctx.send(f"Template `{name}` not found.")

    @template.command(name="preview")
    async def template_preview(self, ctx: commands.Context, name: str):
        rec = await ann_utils.get_template(name)
        if not rec:
            await ctx.send("Template not found.")
            return
        payload = rec.get("content") or {}
        embed = discord.Embed(title=payload.get("title") or "Announcement", description=payload.get("description") or "", color=0x2F3136)
        await ctx.send(embed=embed)

    @announce.command(name="list")
    async def _list(self, ctx: commands.Context):
        """List configured announcements for this guild."""
        items = await ann_utils.list_for_guild(ctx.guild.id)
        if not items:
            await ctx.send("No announcements configured for this server.")
            return
        lines = []
        for it in items:
            sid = it.get("id")
            sa = it.get("scheduled_at")
            enabled = it.get("enabled", True)
            title = (it.get("payload") or {}).get("title")
            lines.append(f"`{sid}` — {title} — scheduled: {sa} — enabled: {enabled}")
        # send paginated if long
        msg = "\n".join(lines[:50])
        await ctx.send(f"Announcements:\n{msg}")

    @announce.command(name="delete")
    async def delete(self, ctx: commands.Context, ann_id: str):
        """Delete an announcement by id."""
        ok = await ann_utils.delete_announcement(ann_id)
        if ok:
            await ctx.send(f"Deleted announcement {ann_id}.")
        else:
            await ctx.send(f"Announcement {ann_id} not found.")

    @announce.command(name="broadcast")
    async def broadcast(self, ctx: commands.Context, scope: str, *, content: str):
        """Owner-only: send an announcement to multiple guilds.

        scope: 'all' to broadcast to all mutual guilds, or a comma-separated list of guild IDs.
        Example: chro announce broadcast all "Title | Body"
        """
        settings = Settings()
        if settings.OWNER_ID is None or ctx.author.id != settings.OWNER_ID:
            await ctx.send("Only the bot owner can use broadcast.")
            return

        # prepare payload
        title = None
        description = content
        if "|" in content:
            parts = content.split("|", 1)
            title = parts[0].strip()
            description = parts[1].strip()
        payload = {"title": title or "Announcement", "description": description}

        targets = []
        if scope.lower() == "all":
            targets = [g.id for g in self.bot.guilds]
        else:
            for part in scope.split(","):
                try:
                    targets.append(int(part.strip()))
                except Exception:
                    continue

        posted = 0
        failed = 0
        for gid in targets:
            guild = self.bot.get_guild(int(gid))
            if not guild:
                failed += 1
                continue
            # choose an announcements channel if configured, else try system channel
            channels = await ann_utils.list_for_guild(gid)
            # prefer configured channel (first), else guild.system_channel
            channel_id = None
            if channels:
                channel_id = channels[0].get("channel_id")
            if channel_id is None and guild.system_channel:
                channel_id = guild.system_channel.id
            if not channel_id:
                failed += 1
                continue
            try:
                ch = guild.get_channel(int(channel_id)) or await self.bot.fetch_channel(int(channel_id))
                embed = discord.Embed(title=payload.get("title"), description=payload.get("description"), color=0x2F3136)
                await ch.send(embed=embed)
                posted += 1
            except Exception:
                failed += 1

        await ctx.send(f"Broadcast complete. Posted: {posted}, failed: {failed}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AnnounceCog(bot))
